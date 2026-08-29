// 签到记录领域状态（Pinia）：收纳账号列表 / 选中账号 / 类型筛选 / 视图模式 / 分页 /
// 日历定位 / 任务列表 / 展开详情。数据来自 B 平台、经后端代理读取（api/signRecords.js），
// 本 store 只做编排。
//
// 账号 / 类型切换走显式 selectAccount / setType，不依赖 watch 隐式链路。
// 日历着色直接用任务列表自带的 finished（isFinishKnowing / isFinishSign）——2026-08-29
// 抓包实证该字段会取 0 表示漏签（如 07.02查寝签到、05.28班会签到），无需再逐任务查
// listLog 聚合，日历因此即时渲染、没有「待聚合」等待。listLog 仅用于展开详情按需拉取。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchAccounts, fetchSignRecords, fetchTaskDetail } from '@/api/signRecords'

// 历史任务量有限（寝/活各自数十~数百级），一次拉全量后在客户端分页，统计口径才与全局一致
const ALL_PAGE_SIZE = 9999

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
  const tasks = ref([]) // 当前账号 + 类型下的全部历史任务（后端已合并排序）

  // 类型筛选：all（全部）| dorm（寝室签到）| activity（活动签到）
  const typeFilter = ref('all')
  // 状态筛选：all（全部）| signed（已签到）| unsigned（未签到）| needPhoto（需拍照）
  const statusFilter = ref('all')
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
  // 任务签到记录缓存：taskId -> { logs, geoFence }，展开详情时按需拉取并复用
  const logsCache = ref({})

  const accountOptions = computed(() =>
    accounts.value.map((a) => ({
      value: toNum(a.id),
      label: a.profile && a.profile.name ? `${a.account} · ${a.profile.name}` : a.account,
    }))
  )

  const selectedAccount = computed(
    () => accounts.value.find((a) => toNum(a.id) === selectedAccountId.value) || null
  )

  // 状态筛选后的任务：统计卡与日历着色的共同口径。
  // 刻意不叠加日历点选的某天（dayFilter）——下钻只是临时查看，不该让概览指标跟着跳变。
  const statusTasks = computed(() => {
    const st = statusFilter.value
    if (st === 'signed') return tasks.value.filter((t) => t.finished)
    if (st === 'unsigned') return tasks.value.filter((t) => !t.finished)
    if (st === 'needPhoto') return tasks.value.filter((t) => t.needPhoto)
    return tasks.value
  })

  // 统计：签到总任务 / 已签到 / 未签到 / 满勤率（与日历口径一致，不受日历点选的某天影响）
  const stats = computed(() => {
    const list = statusTasks.value
    const total = list.length
    const finished = list.filter((t) => t.finished).length
    return {
      total,
      finished,
      unsigned: total - finished,
      needPhoto: list.filter((t) => t.needPhoto).length,
      rate: total ? Math.round((finished / total) * 100) : 0,
    }
  })

  // 列表可见任务：状态筛选之上再叠加日历点选的某天
  const visibleTasks = computed(() => {
    if (!dayFilter.value) return statusTasks.value
    return statusTasks.value.filter((t) =>
      eachDayInRange(t.startDate, t.endDate).includes(dayFilter.value)
    )
  })

  const total = computed(() => visibleTasks.value.length)
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
  const pagedRows = computed(() => {
    const start = (page.value - 1) * pageSize.value
    return visibleTasks.value.slice(start, start + pageSize.value)
  })

  // 每日签到统计：直接按任务自身的 finished（isFinishKnowing / isFinishSign）聚合到日期。
  // overlist 已给出每条任务的签到状态（2026-08-29 抓包实证：isFinishKnowing/isFinishSign
  // 存在 0 值，正是漏签），故无需再逐任务查 listLog —— 日历可即时着色，不再有「待聚合」等待。
  // 同一天可能有多条任务，因此分别统计已签 / 漏签条数。
  const dayStats = computed(() => {
    const acc = {}
    for (const t of statusTasks.value) {
      for (const d of eachDayInRange(t.startDate, t.endDate)) {
        const s = acc[d] || (acc[d] = { signed: 0, unsigned: 0 })
        if (t.finished) s.signed += 1
        else s.unsigned += 1
      }
    }
    return acc
  })

  // 日历网格：以周日为一周起点；当天只要有漏签即标红，全部完成才标绿，无任务为灰
  const calendarWeeks = computed(() => {
    const y = calendarYear.value
    const m = calendarMonth.value
    // 每次重算都取当前时间，避免 store 创建后跨日失效（now 是冻结的初始值）
    const todayStr = fmt(new Date())
    const lead = new Date(y, m - 1, 1).getDay() // 周日=0
    const cells = []
    const cur = new Date(y, m - 1, 1 - lead)
    for (let i = 0; i < 42; i++) {
      const dateStr = fmt(cur)
      const inMonth = cur.getMonth() === m - 1
      const st = dayStats.value[dateStr]
      cells.push({
        date: dateStr,
        day: cur.getDate(),
        inMonth,
        state: !st ? 'none' : st.unsigned > 0 ? 'unsigned' : 'signed',
        signed: st ? st.signed : 0,
        unsigned: st ? st.unsigned : 0,
        today: dateStr === todayStr,
      })
      cur.setDate(cur.getDate() + 1)
    }
    const weeks = []
    for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))
    return weeks
  })

  const calendarLabel = computed(() => `${calendarYear.value}年${calendarMonth.value}月`)
  const isCurrentMonth = computed(() => {
    const d = new Date()
    return calendarYear.value === d.getFullYear() && calendarMonth.value === d.getMonth() + 1
  })
  const monthHasTask = computed(() =>
    calendarWeeks.value.some((w) => w.some((c) => c.state !== 'none'))
  )

  // 最近有数据的月份：取任务区间起点与已签日期中最晚的一个（用于自动跳转 / 一键回到最新）
  const bestDataMonth = computed(() => {
    let best = null
    const consider = (y, m) => {
      if (!best || y > best.y || (y === best.y && m > best.m)) best = { y, m }
    }
    for (const t of statusTasks.value) {
      const s = normalizeDate(t.startDate)
      if (s) {
        const [y, m] = s.split('-').map(Number)
        consider(y, m)
      }
    }
    for (const d of Object.keys(dayStats.value)) {
      const [y, m] = d.split('-').map(Number)
      consider(y, m)
    }
    return best
  })

  // 本月概览（签名元素）：按任务条数统计已签 / 漏签 / 完成率，仅统计当月真实格
  const monthSummary = computed(() => {
    let signed = 0
    let unsigned = 0
    for (const w of calendarWeeks.value) {
      for (const c of w) {
        if (!c.inMonth || c.state === 'none') continue
        signed += c.signed
        unsigned += c.unsigned
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
      details.value = {}
      dayFilter.value = null
      return
    }
    loadingRecords.value = true
    details.value = {}
    page.value = 1
    dayFilter.value = null
    // 账号 / 类型已变，旧的任务签到缓存（展开详情用）作废
    logsCache.value = {}
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
    // 日历着色直接来自任务列表的 finished 字段，无需任何额外聚合请求
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

  function setStatus(s) {
    if (statusFilter.value === s) return
    statusFilter.value = s
    page.value = 1
  }

  function setPage(p) {
    if (p >= 1 && p <= totalPages.value) page.value = p
  }
  function setPageSize(s) {
    pageSize.value = Number(s)
    page.value = 1
  }

  // 切月统一入口：改月份后立即补拉该月所需的签到记录
  function setMonth(y, m) {
    calendarYear.value = y
    calendarMonth.value = m
  }

  function prevMonth() {
    if (calendarMonth.value === 1) setMonth(calendarYear.value - 1, 12)
    else setMonth(calendarYear.value, calendarMonth.value - 1)
  }
  function nextMonth() {
    if (calendarMonth.value === 12) setMonth(calendarYear.value + 1, 1)
    else setMonth(calendarYear.value, calendarMonth.value + 1)
  }
  function backToCurrentMonth() {
    const d = new Date()
    setMonth(d.getFullYear(), d.getMonth() + 1)
  }
  function setDayFilter(d) {
    const next = dayFilter.value === d ? null : d
    dayFilter.value = next
    page.value = 1
    // 在日历里点某天即切到列表看当天明细，省去手动切换视图（取消选中不跳转）
    if (next && viewMode.value === 'calendar') viewMode.value = 'list'
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
      setMonth(best.y, best.m)
    }
  }

  return {
    accounts,
    selectedAccountId,
    loadingAccounts,
    loadingRecords,
    tasks,
    typeFilter,
    statusFilter,
    viewMode,
    page,
    pageSize,
    calendarYear,
    calendarMonth,
    dayFilter,
    details,
    logsCache,
    dayStats,
    accountOptions,
    selectedAccount,
    statusTasks,
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
    setStatus,
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
