// 签到记录领域状态（Pinia）：收纳账号列表 / 选中账号 / 类型筛选 / 视图模式 / 分页 /
// 日历定位 / 任务列表 / 展开详情 / 每日签到聚合。数据来自 B 平台、经后端代理读取
// （api/signRecords.js），本 store 只做编排。
//
// 账号 / 类型切换由 watch 兜底触发 loadRecords，无需在各处手动调用，避免隐式链路遗漏；
// 日历的"哪天没签"来自各任务真实签到记录（listLog）按日期聚合，而非依赖任务区间的
// finished 字段（overlist 仅返回已结束任务，finished 几乎恒为 true，无法体现漏签）。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchAccounts, fetchSignRecords, fetchTaskDetail } from '@/api/signRecords'

// 历史任务量有限（寝/活各自数十~数百级），一次拉全量后在客户端分页，统计口径才与全局一致
const ALL_PAGE_SIZE = 9999
// 并发预拉各任务签到记录的并发度（控制对 B 平台的瞬时压力）
const LOG_CONCURRENCY = 8

// 本地日期格式（避开 toISOString 的 UTC 时区偏移，否则 GMT+8 会差一天）
function fmt(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function toNum(v) {
  const n = Number(v)
  return Number.isNaN(n) ? v : n
}

function normalizeDate(s) {
  if (!s) return null
  const head = String(s).slice(0, 10)
  return /^\d{4}-\d{2}-\d{2}$/.test(head) ? head : null
}

// 展开任务日期区间覆盖的每一天（含端点）；默认单日。上限 92 天，避免长任务淹没整月。
function eachDayInRange(start, end) {
  const out = []
  const s = normalizeDate(start)
  if (!s) return out
  const e = normalizeDate(end) || s
  const cur = new Date(s + 'T00:00:00')
  const last = new Date(e + 'T00:00:00')
  if (isNaN(cur) || isNaN(last)) return out
  let guard = 0
  while (cur <= last && guard < 92) {
    out.push(fmt(cur))
    cur.setDate(cur.getDate() + 1)
    guard++
  }
  return out
}

export const useSignRecordsStore = defineStore('signRecords', () => {
  const accounts = ref([])
  const selectedAccountId = ref(null)
  const loadingAccounts = ref(false)
  const loadingRecords = ref(false)
  const loadingLogs = ref(false)
  // 每日签到聚合是否已完成（false 时日历对应格子显示「待聚合」而非绿/红）
  const logsReady = ref(false)
  const tasks = ref([]) // 当前账号 + 类型下的全部历史任务（后端已合并排序）

  // 类型筛选：all（全部）| dorm（寝室签到）| activity（活动签到）
  const typeFilter = ref('all')
  // 视图模式：list（列表）| calendar（日历）
  const viewMode = ref('list')
  // 列表分页：当前页 / 每页条数（作用于已拉取的全量任务；dayFilter 时作用于当日子集）
  const page = ref(1)
  const pageSize = ref(10)

  // 日历定位：当前查看的年 / 月（1-12），以及点选的某天筛选
  const now = new Date()
  const calendarYear = ref(now.getFullYear())
  const calendarMonth = ref(now.getMonth() + 1)
  const dayFilter = ref(null) // 'YYYY-MM-DD' 或 null

  // 展开详情：taskId -> { loading, open, geoFence, logs, error }
  const details = ref({})
  // 任务签到记录缓存：taskId -> { logs, geoFence }，预拉后供展开复用
  const logsCache = ref({})
  // 每日签到聚合：'YYYY-MM-DD' -> 当天签到次数（来自各任务 listLog 真实数据）
  const signedByDate = ref({})
  // 预拉轮次标记，屏蔽过期轮次对缓存的覆盖
  const logsRun = ref(0)

  const accountOptions = computed(() =>
    accounts.value.map((a) => ({
      value: toNum(a.id),
      label: a.profile && a.profile.name ? `${a.account} · ${a.profile.name}` : a.account,
    }))
  )

  const selectedAccount = computed(
    () => accounts.value.find((a) => toNum(a.id) === selectedAccountId.value) || null
  )

  // 统计：基于当前账号 + 类型的全量任务（已拉全，非仅当前页，也不受日历日筛选影响）
  const stats = computed(() => {
    const list = tasks.value
    return {
      total: list.length,
      finished: list.filter((t) => t.finished).length,
      needPhoto: list.filter((t) => t.needPhoto).length,
    }
  })

  // 列表可见任务：点选某天时仅保留区间覆盖该天的任务
  const visibleTasks = computed(() => {
    if (!dayFilter.value) return tasks.value
    return tasks.value.filter((t) =>
      eachDayInRange(t.startDate, t.endDate).includes(dayFilter.value)
    )
  })

  const total = computed(() => visibleTasks.value.length)
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
  const pagedRows = computed(() => {
    const start = (page.value - 1) * pageSize.value
    return visibleTasks.value.slice(start, start + pageSize.value)
  })

  // 日历网格：以周日为一周起点（对齐旧版 UI）；每日：有任务且当天有真实签到→已签(绿)，
  // 有任务但无签到→漏签(红)，其余→无记录(灰)。签到数据来自预拉的 listLog 真实聚合。
  const calendarWeeks = computed(() => {
    const y = calendarYear.value
    const m = calendarMonth.value
    const taskDays = {}
    for (const t of tasks.value) {
      for (const d of eachDayInRange(t.startDate, t.endDate)) taskDays[d] = true
    }
    const lead = new Date(y, m - 1, 1).getDay() // 周日=0
    const cells = []
    const cur = new Date(y, m - 1, 1 - lead)
    for (let i = 0; i < 42; i++) {
      const dateStr = fmt(cur)
      const inMonth = cur.getMonth() === m - 1
      const hasTask = !!taskDays[dateStr]
      const signed = signedByDate.value[dateStr] || 0
      let state
      if (!hasTask) state = 'none'
      else if (!logsReady.value) state = 'pending'
      else state = signed > 0 ? 'signed' : 'unsigned'
      cells.push({
        date: dateStr,
        day: cur.getDate(),
        inMonth,
        state,
        signed,
        unsigned: hasTask && signed === 0 ? 1 : 0,
      })
      cur.setDate(cur.getDate() + 1)
    }
    const weeks = []
    for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))
    return weeks
  })

  const calendarLabel = computed(() => `${calendarYear.value}年${calendarMonth.value}月`)
  const isCurrentMonth = computed(
    () => calendarYear.value === now.getFullYear() && calendarMonth.value === now.getMonth() + 1
  )
  const monthHasTask = computed(() =>
    calendarWeeks.value.some((w) => w.some((c) => c.state !== 'none'))
  )

  // 最近有数据的月份：取任务区间起点与已签日期中最晚的一个（用于自动跳转 / 一键回到最新）
  const bestDataMonth = computed(() => {
    let best = null
    const consider = (y, m) => {
      if (!best || y > best.y || (y === best.y && m > best.m)) best = { y, m }
    }
    for (const t of tasks.value) {
      const s = normalizeDate(t.startDate)
      if (s) {
        const [y, m] = s.split('-').map(Number)
        consider(y, m)
      }
    }
    for (const d of Object.keys(signedByDate.value)) {
      const [y, m] = d.split('-').map(Number)
      consider(y, m)
    }
    return best
  })

  // 本月概览（签名元素）：已签 / 漏签 / 完成率，仅统计当月真实格
  const monthSummary = computed(() => {
    let signed = 0
    let unsigned = 0
    for (const w of calendarWeeks.value) {
      for (const c of w) {
        if (!c.inMonth || c.state === 'none' || c.state === 'pending') continue
        if (c.state === 'signed') signed++
        else if (c.state === 'unsigned') unsigned++
      }
    }
    const total = signed + unsigned
    const rate = total ? Math.round((signed / total) * 100) : 0
    return { signed, unsigned, total, rate }
  })

  async function loadAccounts() {
    loadingAccounts.value = true
    try {
      const list = await fetchAccounts()
      accounts.value = list
      if (list.length) {
        if (!selectedAccountId.value || !list.some((a) => toNum(a.id) === selectedAccountId.value)) {
          selectedAccountId.value = toNum(list[0].id)
        }
      } else {
        selectedAccountId.value = null
      }
    } finally {
      loadingAccounts.value = false
    }
    // 选中态就绪后再拉记录（初始加载与后续切换都走这里，不再依赖 watch）
    await loadRecords()
  }

  async function loadRecords() {
    if (!selectedAccountId.value) {
      tasks.value = []
      logsCache.value = {}
      signedByDate.value = {}
      logsReady.value = true
      details.value = {}
      dayFilter.value = null
      return
    }
    loadingRecords.value = true
    details.value = {}
    page.value = 1
    dayFilter.value = null
    try {
      const res = await fetchSignRecords(selectedAccountId.value, {
        type: typeFilter.value,
        page: 1,
        pageSize: ALL_PAGE_SIZE,
      })
      tasks.value = res.items || []
      // 当前月无数据则自动跳到最近有数据的月份，避免日历一片空白
      syncCalendarToData()
    } finally {
      loadingRecords.value = false
    }
    // 列表已可渲染；日历所需的每日签到聚合在后台并发预拉，logsReady/loadingLogs 单独指示
    logsReady.value = false
    void loadAllLogs()
  }

  // 并发预拉各任务真实签到记录，按 log.time 日期聚合到 signedByDate，
  // 结果缓存到 logsCache 供展开详情复用。幂等轮次标记防止过期轮次覆盖新数据。
  async function loadAllLogs() {
    const list = tasks.value
    if (!list.length) {
      logsCache.value = {}
      signedByDate.value = {}
      logsReady.value = true
      return
    }
    const myRun = ++logsRun.value
    loadingLogs.value = true
    const cache = {}
    const acc = {}
    let idx = 0
    const worker = async () => {
      while (idx < list.length) {
        const t = list[idx++]
        try {
          const r = await fetchTaskDetail(selectedAccountId.value, t.id, t.kind)
          cache[t.id] = { logs: r.logs || [], geoFence: r.geoFence || [] }
          for (const lg of r.logs || []) {
            const d = normalizeDate(lg.time)
            if (d) acc[d] = (acc[d] || 0) + 1
          }
        } catch (e) {
          cache[t.id] = { logs: [], geoFence: [] }
        }
      }
    }
    await Promise.all(Array.from({ length: Math.min(LOG_CONCURRENCY, list.length) }, worker))
    if (myRun === logsRun.value) {
      logsCache.value = cache
      signedByDate.value = acc
      logsReady.value = true
    }
    // 本轮为最新轮次才收尾；过期轮次由新轮次自行收尾，避免旧数据覆盖
    if (myRun === logsRun.value) loadingLogs.value = false
  }

  function setType(t) {
    if (typeFilter.value === t) return
    typeFilter.value = t
    page.value = 1
    dayFilter.value = null
    loadRecords()
  }

  function setView(v) {
    if (viewMode.value === v) return
    viewMode.value = v
    page.value = 1
  }

  function setPage(p) {
    if (p >= 1 && p <= totalPages.value) page.value = p
  }
  function setPageSize(s) {
    pageSize.value = Number(s)
    page.value = 1
  }

  function prevMonth() {
    if (calendarMonth.value === 1) {
      calendarMonth.value = 12
      calendarYear.value--
    } else {
      calendarMonth.value--
    }
  }
  function nextMonth() {
    if (calendarMonth.value === 12) {
      calendarYear.value = 1
      calendarMonth.value++
    } else {
      calendarMonth.value++
    }
  }
  function backToCurrentMonth() {
    calendarYear.value = now.getFullYear()
    calendarMonth.value = now.getMonth() + 1
  }
  function setDayFilter(d) {
    dayFilter.value = dayFilter.value === d ? null : d
    page.value = 1
  }
  function clearDayFilter() {
    dayFilter.value = null
    page.value = 1
  }

  // 展开 / 收起：优先用预拉缓存，否则懒加载地理围栏 + 签到记录
  async function toggleExpand(task) {
    const id = task.id
    const cur = details.value[id]
    if (cur && cur.open) {
      details.value = { ...details.value, [id]: { ...cur, open: false } }
      return
    }
    const cached = logsCache.value[id]
    if (cached) {
      details.value = {
        ...details.value,
        [id]: { loading: false, open: true, geoFence: cached.geoFence, logs: cached.logs, error: '' },
      }
      return
    }
    details.value = { ...details.value, [id]: { loading: true, open: true, geoFence: [], logs: [], error: '' } }
    try {
      const res = await fetchTaskDetail(selectedAccountId.value, id, task.kind)
      logsCache.value = { ...logsCache.value, [id]: { logs: res.logs, geoFence: res.geoFence } }
      details.value = {
        ...details.value,
        [id]: { loading: false, open: true, geoFence: res.geoFence, logs: res.logs, error: '' },
      }
    } catch (e) {
      details.value = {
        ...details.value,
        [id]: { loading: false, open: true, geoFence: [], logs: [], error: e.message || '加载详情失败' },
      }
    }
  }

  function getDetail(id) {
    return details.value[id] || null
  }

  // 账号切换：显式写回并重新拉取（去掉脆弱的 watch 隐式链路，避免遗漏触发）
  function selectAccount(id) {
    const nid = toNum(id)
    if (selectedAccountId.value === nid) return
    selectedAccountId.value = nid
    dayFilter.value = null
    page.value = 1
    void loadRecords()
  }

  // 当前月无数据则自动跳到最近有数据的月份（基于任务区间与已签日期取最晚月份）
  function syncCalendarToData() {
    if (!tasks.value.length) return
    const hasCurrent = calendarWeeks.value.some((w) =>
      w.some((c) => c.inMonth && c.state !== 'none')
    )
    if (hasCurrent) return
    const best = bestDataMonth.value
    if (best) {
      calendarYear.value = best.y
      calendarMonth.value = best.m
    }
  }

  // 手动跳到最近有数据的月份
  function jumpToBestMonth() {
    const best = bestDataMonth.value
    if (best) {
      dayFilter.value = null
      calendarYear.value = best.y
      calendarMonth.value = best.m
    }
  }

  return {
    accounts,
    selectedAccountId,
    loadingAccounts,
    loadingRecords,
    loadingLogs,
    logsReady,
    tasks,
    typeFilter,
    viewMode,
    page,
    pageSize,
    calendarYear,
    calendarMonth,
    dayFilter,
    details,
    logsCache,
    signedByDate,
    accountOptions,
    selectedAccount,
    stats,
    visibleTasks,
    total,
    totalPages,
    pagedRows,
    calendarWeeks,
    calendarLabel,
    isCurrentMonth,
    monthHasTask,
    bestDataMonth,
    monthSummary,
    loadAccounts,
    loadRecords,
    selectAccount,
    setType,
    setView,
    setPage,
    setPageSize,
    prevMonth,
    nextMonth,
    backToCurrentMonth,
    jumpToBestMonth,
    setDayFilter,
    clearDayFilter,
    toggleExpand,
    getDetail,
  }
})
