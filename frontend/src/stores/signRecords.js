// 签到记录领域状态（Pinia）：收纳账号列表 / 选中账号 / 类型与状态筛选 / 视图模式 /
// 服务端分页 / 日历定位 / 任务列表 / 展开详情。数据来自 B 平台、经后端代理读取
// （api/signRecords.js），本 store 只做编排。
//
// [数据口径（服务端分页改造）]
// - 列表：page/pageSize/type/status/日期窗口全部由后端筛选分页，前端不再全量拉取；
//   统计卡（overview）与最近数据月份（meta.latest）由后端按全历史口径随每次响应返回，
//   与「统计跟随状态筛选、不受日历点选影响」的原口径一致。
// - 日历：按 42 格网格窗口（date_from=首格日、date_to=末格日）向后端取当窗任务，
//   前端按任务区间展开着色；结果按 账号|类型|状态|年月 缓存，切月不重复请求。
// - 竞态守卫：列表请求带序号、日历请求带 key 比对，仅采纳最新一次的结果，
//   杜绝快速切换账号/类型时旧响应覆盖新数据。
//
// 日历着色直接用任务列表自带的 finished（isFinishKnowing / isFinishSign）——2026-08-29
// 抓包实证该字段会取 0 表示漏签，无需逐任务查 listLog；listLog 仅用于展开详情按需拉取。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchAccounts, fetchSignRecords, fetchTaskDetail } from '@/api/signRecords'

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

// 展开任务日期区间覆盖的每一天（含端点）；默认单日。上限 92 天，避免长任务淹没日历。
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

const EMPTY_OVERVIEW = { total: 0, finished: 0, unsigned: 0, needPhoto: 0, rate: 0 }

export const useSignRecordsStore = defineStore('signRecords', () => {
  const accounts = ref([])
  const selectedAccountId = ref(null)
  const loadingAccounts = ref(false)
  const loadingRecords = ref(false)
  const loadingCalendar = ref(false)
  // 当前列表页数据（服务端分页的一页）与服务端总数
  const tasks = ref([])
  const total = ref(0)
  // 全历史口径统计（后端随列表响应返回，status 筛选跟随、日期窗口不影响）
  const overview = ref({ ...EMPTY_OVERVIEW })
  // 全历史口径最近有任务的日期（'YYYY-MM-DD'，驱动日历「最近有数据月份」）
  const dataLatest = ref(null)

  // 类型筛选：all（全部）| dorm（寝室签到）| activity（活动签到）
  const typeFilter = ref('all')
  // 状态筛选：all（全部）| signed（已签到）| unsigned（未签到）| needPhoto（需拍照）
  const statusFilter = ref('all')
  // 视图模式：list（列表）| calendar（日历）
  const viewMode = ref('list')
  // 列表分页：当前页 / 每页条数（服务端分页）
  const page = ref(1)
  const pageSize = ref(10)

  // 日历定位：当前查看的年 / 月（1-12），以及点选的某天筛选
  const now = new Date()
  const calendarYear = ref(now.getFullYear())
  const calendarMonth = ref(now.getMonth() + 1)
  const dayFilter = ref(null) // 'YYYY-MM-DD' 或 null

  // 日历月份数据缓存：`${accountId}|${type}|${status}|${y}-${m}` -> 日期聚合
  // （key 含筛选维度，天然隔离，无需手动失效）
  const monthCache = ref({})
  const monthKey = computed(
    () =>
      `${selectedAccountId.value}|${typeFilter.value}|${statusFilter.value}|` +
      `${calendarYear.value}-${String(calendarMonth.value).padStart(2, '0')}`
  )
  const monthDays = computed(() => monthCache.value[monthKey.value] || null)

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

  // 统计卡口径：后端全历史统计（type+status 过滤，与日历口径一致、不受日历点选影响）
  const stats = computed(() => overview.value)

  // 列表当前页（服务端分页结果；保留 pagedRows 名称以维持视图契约）
  const pagedRows = computed(() => tasks.value)

  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

  // 每日签到统计：由日历窗口内任务按自身 finished 聚合到日期（服务端已按窗口取数）
  const dayStats = computed(() => monthDays.value || {})

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

  // 最近有数据的月份：后端 meta.latest_date（全历史口径），用于自动跳转 / 一键回到最新
  const bestDataMonth = computed(() => {
    const d = dataLatest.value
    if (!d) return null
    const [y, m] = d.split('-').map(Number)
    return { y, m }
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
    const total2 = signed + unsigned
    const rate = total2 ? Math.round((signed / total2) * 100) : 0
    return { signed, unsigned, total: total2, rate }
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

  // 拉取列表页（服务端分页）。dayFilter 点选时窗口收窄为当天，统计卡仍为全历史口径
  let listSeq = 0
  async function loadList() {
    if (!selectedAccountId.value) {
      tasks.value = []
      total.value = 0
      overview.value = { ...EMPTY_OVERVIEW }
      dataLatest.value = null
      return
    }
    const seq = ++listSeq
    const day = dayFilter.value
    loadingRecords.value = true
    try {
      const res = await fetchSignRecords(selectedAccountId.value, {
        type: typeFilter.value,
        status: statusFilter.value,
        page: page.value,
        pageSize: pageSize.value,
        dateFrom: day || undefined,
        dateTo: day || undefined,
      })
      if (seq !== listSeq) return // 竞态守卫：仅采纳最新请求
      tasks.value = res.items
      total.value = res.total
      if (res.overview) overview.value = res.overview
      if (res.meta && res.meta.latest_date) dataLatest.value = res.meta.latest_date
    } finally {
      if (seq === listSeq) loadingRecords.value = false
    }
  }

  // 拉取日历 42 格网格窗口的任务并聚合着色（按 账号|类型|状态|年月 缓存）
  let monthSeq = 0
  async function loadMonth() {
    if (!selectedAccountId.value) return
    const key = monthKey.value
    if (monthCache.value[key]) return
    const seq = ++monthSeq
    const y = calendarYear.value
    const m = calendarMonth.value
    const lead = new Date(y, m - 1, 1).getDay() // 周日=0
    const first = new Date(y, m - 1, 1 - lead)
    const last = new Date(first)
    last.setDate(first.getDate() + 41)
    loadingCalendar.value = true
    try {
      const res = await fetchSignRecords(selectedAccountId.value, {
        type: typeFilter.value,
        status: statusFilter.value,
        page: 1,
        pageSize: 200, // 单月窗口内的任务量级，200 足够（后端上限 200）
        dateFrom: fmt(first),
        dateTo: fmt(last),
      })
      if (seq !== monthSeq || key !== monthKey.value) return // 切月竞态守卫
      const acc = {}
      for (const t of res.items) {
        for (const d of eachDayInRange(t.startDate, t.endDate)) {
          const s = acc[d] || (acc[d] = { signed: 0, unsigned: 0 })
          if (t.finished) s.signed += 1
          else s.unsigned += 1
        }
      }
      monthCache.value = { ...monthCache.value, [key]: acc }
    } finally {
      if (seq === monthSeq) loadingCalendar.value = false
    }
  }

  // 账号/类型切换的整备动作：重置分页与日历点选、作废展开缓存，列表与日历各拉各的
  async function loadRecords() {
    details.value = {}
    page.value = 1
    dayFilter.value = null
    logsCache.value = {}
    await Promise.all([loadList(), loadMonth()])
    // 当前月无数据则自动跳到最近有数据的月份，避免日历一片空白
    syncCalendarToData()
  }

  function setType(t) {
    if (typeFilter.value === t) return
    typeFilter.value = t
    loadRecords()
  }

  function setView(v) {
    if (viewMode.value === v) return
    viewMode.value = v
    page.value = 1
  }

  // 状态筛选已下沉服务端：切换即重新拉列表与日历（统计卡由后端 overview 直接给出）
  function setStatus(s) {
    if (statusFilter.value === s) return
    statusFilter.value = s
    page.value = 1
    dayFilter.value = null
    void loadList()
    void loadMonth()
  }

  function setPage(p) {
    if (p >= 1 && p <= totalPages.value && p !== page.value) {
      page.value = p
      void loadList()
    }
  }
  function setPageSize(s) {
    const n = Number(s)
    if (n === pageSize.value) return
    pageSize.value = n
    page.value = 1
    void loadList()
  }

  // 切月统一入口：改月份后补拉该月日历数据（有缓存即命中，不发请求）
  function setMonth(y, m) {
    calendarYear.value = y
    calendarMonth.value = m
    void loadMonth()
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
    void loadList()
    // 在日历里点某天即切到列表看当天明细，省去手动切换视图（取消选中不跳转）
    if (next && viewMode.value === 'calendar') viewMode.value = 'list'
  }
  function clearDayFilter() {
    dayFilter.value = null
    page.value = 1
    void loadList()
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

  // 当前月无数据则自动跳到最近有数据的月份（后端 meta.latest_date，全历史口径）
  function syncCalendarToData() {
    if (!dataLatest.value) return
    const cached = monthCache.value[monthKey.value]
    if (cached && Object.keys(cached).length) return
    const [y, m] = dataLatest.value.split('-').map(Number)
    calendarYear.value = y
    calendarMonth.value = m
    void loadMonth()
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
    loadingCalendar,
    tasks,
    total,
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
    stats,
    pagedRows,
    totalPages,
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
