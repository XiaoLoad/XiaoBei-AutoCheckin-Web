// 用户日志领域状态（Pinia）：编排平台操作审计流水与「会话段」两种视图。
// 与任务日志的区别：任务日志是「机器替用户做了什么」，本页是「人做了什么」，
// 故筛选维度是操作者/动作/结果，而不是账号/签到类型。
//
// 两个视图的数据同源（同一批 op_logs），只是投影不同：
//   会话 —— 成功登录 → 登出之间的一切操作归一段，回答「他这次进来都干了什么」；
//   流水 —— 按时间倒序的平铺事件，回答「某件事发生在什么时候」。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRefreshBusStore } from '@/stores/refreshBus'
import {
  ackOpLogAnomalies,
  fetchOpLogs,
  fetchOpLogMeta,
  fetchOpLogSessions,
  fetchOpLogSummary,
} from '@/api/opLogs'
import { opDateKey, opDayLabel, opLocalDate } from '@/utils/opLogMeta'

const RANGE_DAYS = 30
// 导出：逐批取流水（接口单页上限 100），累加到上限为止。
// 导出的是「符合当前筛选的事件」而非当前视图的投影——CSV 一行一事件才能被表格工具处理，
// 会话卡那种嵌套结构在 CSV 里表达不出来。
const EXPORT_BATCH = 100
const EXPORT_CAP = 1000

// 默认筛选：近 30 天。审计页不加默认时间窗会把整表拉出来，
// 既慢又没意义——「谁改了什么」这个问题天然是近期导向的。
function defaultFilters() {
  const to = new Date()
  const from = new Date(to.getTime() - (RANGE_DAYS - 1) * 86400000)
  return {
    keyword: '',
    action: '',
    result: '',
    dateFrom: opLocalDate(from),
    dateTo: opLocalDate(to),
  }
}

export const useOpLogsStore = defineStore('opLogs', () => {
  const refreshBus = useRefreshBusStore()

  // 视图：会话优先（设计稿默认停在会话），流水是补充视角
  const view = ref('session')
  const filters = ref(defaultFilters())
  const page = ref(1)
  // 会话卡比流水行高得多，一页 10 段更适合逐段读；流水视图可自行调到 50
  const pageSize = ref(10)

  const logs = ref([])
  const total = ref(0)
  const sessions = ref([])
  const sessionTotal = ref(0)

  const metrics = ref({ loginToday: 0, loginFailToday: 0, userChangeToday: 0, ongoingSessions: 0 })
  const anomalies = ref([])
  // 已被本账号确认压住的来源 IP：关掉的东西仍要看得见，
  // 否则「已处理」和「被删掉」在界面上没有区别
  const ackedQuiet = ref([])
  const anomalyWindowDays = ref(7)
  const retentionDays = ref(365)
  const meta = ref({ categories: [], actions: [] })

  const loading = ref(false)
  const refreshing = ref(false)
  const loaded = ref(false)
  // 指标与列表走两个接口：指标未到位时卡片显示骨架，但不阻塞列表浏览
  const summaryLoaded = ref(false)
  const exporting = ref(false)
  // 「标记已处理」进行中：按钮要禁用并显示处理文案，否则连点会发两次确认
  const acking = ref(false)
  // 展开态的唯一真相：同一时刻至多展开一条（手风琴），条目上不另存 open 标记
  const expandedId = ref(null)
  let seq = 0
  // 筛选项只做「请求在飞去重」，不做会话内一次性缓存：一次性门闩会把项集合与
  // 「（计数）」冻结在首次进页面那一刻，管理员刚删了用户再回到本页，下拉里的数字还是旧的。
  let metaInflight = null

  const isSession = computed(() => view.value === 'session')

  // 按日分段：仅「流水」视图使用。注意分组范围是当前页（服务端分页），
  // 故分节带不展示「当日共 N 条」这类总数，否则跨页会给出互相矛盾的数字。
  const groups = computed(() => {
    const out = []
    let cur = null
    for (const row of logs.value) {
      const day = opDateKey(row.createdAt) || 'unknown'
      if (!cur || cur.day !== day) {
        cur = { day, label: opDayLabel(day === 'unknown' ? '' : day), items: [] }
        out.push(cur)
      }
      cur.items.push(row)
    }
    return out
  })

  // 快捷区间当前命中哪一个（都不命中则返回空，日期按钮上不加高亮）
  const quickRange = computed(() => {
    const { dateFrom, dateTo } = filters.value
    const today = opLocalDate(new Date())
    const preset = (days) => {
      const from = new Date(Date.now() - (days - 1) * 86400000)
      return { from: opLocalDate(from), to: today }
    }
    for (const [key, days] of [['today', 1], ['7d', 7], ['30d', RANGE_DAYS]]) {
      const p = preset(days)
      if (dateFrom === p.from && dateTo === p.to) return key
    }
    return ''
  })

  // 「重置」按钮的显示条件：偏离默认态才算有筛选，否则按了也没变化
  const hasFilter = computed(() => {
    const d = defaultFilters()
    const f = filters.value
    return f.keyword !== '' || f.action !== '' || f.result !== ''
      || f.dateFrom !== d.dateFrom || f.dateTo !== d.dateTo
  })

  function toParams() {
    const f = filters.value
    const p = { page: page.value, page_size: pageSize.value }
    if (f.keyword) p.keyword = f.keyword
    if (f.action) p.action = f.action
    if (f.result) p.result = f.result
    if (f.dateFrom) p.date_from = f.dateFrom
    if (f.dateTo) p.date_to = f.dateTo
    return p
  }

  async function loadCurrent() {
    const first = !loaded.value
    if (first) loading.value = true
    else {
      refreshing.value = true
      refreshBus.begin()
    }
    const mine = ++seq
    try {
      if (isSession.value) {
        const res = await fetchOpLogSessions(toParams())
        if (mine !== seq) return // 竞态守卫：仅采纳最新一次请求
        sessions.value = res.items
        sessionTotal.value = res.total
      } else {
        const res = await fetchOpLogs(toParams())
        if (mine !== seq) return
        logs.value = res.items
        total.value = res.total
      }
      expandedId.value = null // 列表换新，旧的展开项已不属于当前页
      loaded.value = true
    } catch (e) {
      if (mine !== seq) return
      if (isSession.value) {
        sessions.value = []
        sessionTotal.value = 0
      } else {
        logs.value = []
        total.value = 0
      }
    } finally {
      if (!first) refreshBus.end()
      if (mine === seq) {
        loading.value = false
        refreshing.value = false
      }
    }
  }

  async function loadSummary() {
    try {
      const res = await fetchOpLogSummary()
      metrics.value = res.metrics
      anomalies.value = res.anomalies
      ackedQuiet.value = res.ackedQuiet
      anomalyWindowDays.value = res.anomalyWindowDays
      retentionDays.value = res.retentionDays
      summaryLoaded.value = true
    } catch (e) {
      /* 指标取不到不影响列表浏览，保留上次数值（首屏为 0） */
    }
  }

  // 标记异常告警为已处理：确认依据（当时的失败次数）由服务端现算，
  // 前端只报「处理哪些 IP」，免得界面自己决定它什么时候再提醒自己。
  // 成功后重取 summary，让横幅与「已处理 N 个」的说明同步落到位。
  async function ackAnomalies(ips) {
    if (acking.value) return false
    acking.value = true
    try {
      await ackOpLogAnomalies(ips)
      await loadSummary()
      return true
    } finally {
      acking.value = false
    }
  }

  async function loadMeta() {
    if (metaInflight) return metaInflight
    metaInflight = (async () => {
      try {
        meta.value = await fetchOpLogMeta()
      } catch (e) {
        /* 筛选项取不到不影响浏览，保留上一次的候选 */
      } finally {
        metaInflight = null
      }
    })()
    return metaInflight
  }

  // 任一筛选变化都要回到第一页，否则会停在越界页拿到空列表
  function applyFilter(patch) {
    filters.value = { ...filters.value, ...patch }
    page.value = 1
    loadCurrent()
  }

  // 快捷区间：今天 / 近 7 天 / 近 30 天，直接覆盖日期两端
  function setQuickRange(key) {
    const today = opLocalDate(new Date())
    const days = key === 'today' ? 1 : key === '7d' ? 7 : RANGE_DAYS
    applyFilter({
      dateFrom: opLocalDate(new Date(Date.now() - (days - 1) * 86400000)),
      dateTo: today,
    })
  }

  function resetFilters() {
    if (!hasFilter.value) return
    filters.value = defaultFilters()
    page.value = 1
    loadCurrent()
  }

  function setView(next) {
    if (view.value === next) return
    view.value = next
    page.value = 1
    loadCurrent()
  }

  function setPage(p) {
    page.value = p
    loadCurrent()
  }

  function setPageSize(s) {
    pageSize.value = Number(s)
    page.value = 1
    loadCurrent()
  }

  function toggleDetail(row) {
    const id = row && row.id != null ? row.id : null
    if (id == null) return
    expandedId.value = expandedId.value === id ? null : id
  }

  // 导出用数据集：按当前筛选逐批拉取，上限 EXPORT_CAP 条。
  // 返回 total 与 truncated，让调用方能把「还有多少条没导出」如实告诉用户——
  // 悄悄截断的导出比不导出更糟，用户会以为拿到的是全部。
  async function exportRows() {
    if (exporting.value) return null
    exporting.value = true
    try {
      const base = toParams()
      delete base.page
      delete base.page_size
      const first = await fetchOpLogs({ ...base, page: 1, page_size: EXPORT_BATCH })
      const need = Math.min(first.total, EXPORT_CAP)
      let items = first.items
      let p = 1
      while (items.length < need) {
        p += 1
        const res = await fetchOpLogs({ ...base, page: p, page_size: EXPORT_BATCH })
        if (!res.items.length) break // 数据在翻页途中被清理，就此收手
        items = items.concat(res.items)
      }
      return { items: items.slice(0, need), total: first.total, truncated: first.total > need }
    } finally {
      exporting.value = false
    }
  }

  // 进页面与手动刷新走同一条路径：两者都该拿到「此刻最新」的筛选项与指标。
  // 曾经 init 拉 meta 而 refresh 不拉——刷新后列表是最新的，下拉里的计数却还是旧的。
  async function refresh() {
    await Promise.all([loadMeta(), loadSummary(), loadCurrent()])
  }

  async function init() {
    await refresh()
  }

  return {
    view,
    filters,
    page,
    pageSize,
    logs,
    total,
    sessions,
    sessionTotal,
    metrics,
    anomalies,
    ackedQuiet,
    anomalyWindowDays,
    retentionDays,
    meta,
    loading,
    refreshing,
    loaded,
    summaryLoaded,
    exporting,
    acking,
    expandedId,
    isSession,
    groups,
    quickRange,
    hasFilter,
    init,
    refresh,
    loadCurrent,
    loadSummary,
    loadMeta,
    applyFilter,
    setQuickRange,
    resetFilters,
    setView,
    setPage,
    setPageSize,
    toggleDetail,
    exportRows,
    ackAnomalies,
  }
})
