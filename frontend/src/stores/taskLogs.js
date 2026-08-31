// 任务日志领域状态（Pinia）：编排全局跨账号执行日志（sign_records 本地流水）。
// 账号列表复用 accounts API，供执行日志筛选器使用。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchAccounts } from '@/api/accounts'
import { fetchTaskLogs, fetchTaskLogDetail, deleteTaskLog, purgeTaskLogs } from '@/api/taskLogs'

function toNum(v) {
  const n = Number(v)
  return Number.isNaN(n) ? v : n
}

export const useTaskLogsStore = defineStore('taskLogs', () => {
  // 账号（执行日志筛选共用）
  const accounts = ref([])
  const selectedAccountId = ref(null)
  const loadingAccounts = ref(false)

  // 执行日志：筛选与分页
  const typeFilter = ref('all')
  const statusFilter = ref('all')
  const page = ref(1)
  const pageSize = ref(10)
  const logs = ref([])
  const total = ref(0)
  const overview = ref({ total: 0, success: 0, fail: 0, skip: 0 })
  const loadingLogs = ref(false)
  // 无感刷新：已有日志时后台静默换新（视图仅降透明），loadingLogs 只用于真正的首次加载
  const refreshingLogs = ref(false)
  const logsLoaded = ref(false)
  let logsSeq = 0

  // 展开详情（手风琴）：details 按日志 id 缓存 { loading, error, data }，
  // expandedId 是当前唯一展开项，展开新的会先收起旧的，故同一时刻至多一项展开。
  const details = ref({})
  const expandedId = ref(null)

  const accountOptions = computed(() =>
    accounts.value.map((a) => ({
      value: toNum(a.id),
      label: a.profile && a.profile.name ? `${a.account} · ${a.profile.name}` : a.account,
    }))
  )

  async function loadAccounts() {
    loadingAccounts.value = true
    try {
      const list = await fetchAccounts()
      accounts.value = list
      // 默认「全部账号」：任务日志是全局跨账号视图，不预先锁定单个账号（否则会隐藏其余账号记录）
    } finally {
      loadingAccounts.value = false
    }
  }

  async function loadLogs() {
    const first = !logsLoaded.value
    if (first) loadingLogs.value = true
    else refreshingLogs.value = true
    const seq = ++logsSeq
    try {
      const res = await fetchTaskLogs({
        accountId: selectedAccountId.value || '',
        type: typeFilter.value,
        status: statusFilter.value,
        page: page.value,
        pageSize: pageSize.value,
      })
      if (seq !== logsSeq) return // 竞态守卫：仅采纳最新请求
      logs.value = res.items || []
      // 列表整体换新：旧的展开态与详情缓存一并作废，避免留着不属于当前页的展开项
      resetDetails()
      total.value = res.total || 0
      overview.value = res.overview || { total: 0, success: 0, fail: 0, skip: 0 }
      logsLoaded.value = true
    } catch (e) {
      if (seq !== logsSeq) return
      logs.value = []
      total.value = 0
      overview.value = { total: 0, success: 0, fail: 0, skip: 0 }
    } finally {
      if (seq === logsSeq) {
        loadingLogs.value = false
        refreshingLogs.value = false
      }
    }
  }

  // ---- 展开详情：手风琴（同一时刻至多一项展开）----
  function detailOf(id) {
    return details.value[id] || null
  }

  function isOpen(id) {
    return expandedId.value === id
  }

  function resetDetails() {
    details.value = {}
    expandedId.value = null
  }

  // 展开态的唯一真相是 expandedId，条目上不再另存 open 标记，杜绝两处状态不同步
  function closeDetail() {
    expandedId.value = null
  }

  // 点已展开项即收起；点另一项先收起旧项再展开新项，保证「展开一个自动收回其它」
  async function toggleDetail(row) {
    const id = row && row.id != null ? row.id : null
    if (id == null) return
    if (expandedId.value === id) {
      closeDetail()
      return
    }
    closeDetail()
    if (!details.value[id]) {
      details.value[id] = { loading: false, error: '', data: null }
    }
    expandedId.value = id
    await ensureDetail(id)
  }

  // 按需拉取并缓存：已拿到数据或正在拉取时不再重复请求
  async function ensureDetail(id) {
    const d = details.value[id]
    if (!d || d.data || d.loading) return
    d.loading = true
    d.error = ''
    try {
      d.data = await fetchTaskLogDetail(id)
    } catch (e) {
      d.error = e.message || '加载配置详情失败'
    } finally {
      d.loading = false
    }
  }

  function selectAccount(id) {
    const nid = id == null ? null : toNum(id)
    if (selectedAccountId.value === nid) return
    selectedAccountId.value = nid
    page.value = 1
    loadLogs()
  }

  function setType(t) {
    if (typeFilter.value === t) return
    typeFilter.value = t
    page.value = 1
    loadLogs()
  }
  function setStatus(s) {
    if (statusFilter.value === s) return
    statusFilter.value = s
    page.value = 1
    loadLogs()
  }
  function setPage(p) {
    page.value = p
    loadLogs()
  }
  function setPageSize(s) {
    pageSize.value = Number(s)
    page.value = 1
    loadLogs()
  }

  async function init() {
    await loadAccounts()
    await loadLogs()
  }

  // 删除单条本人日志（后端校验归属），成功后刷新当前列表
  async function removeLog(id) {
    await deleteTaskLog(id)
    await loadLogs()
  }

  // 批量清理本人日志：before 必填（YYYY-MM-DD），可选叠加账号/类型/状态过滤
  async function purgeBefore(before, { accountId, type, status } = {}) {
    const res = await purgeTaskLogs({ before, accountId, type, status })
    page.value = 1
    await loadLogs()
    return res  // 透出 { deleted } 供视图提示清理条数（此前漏 return 致视图读 undefined.deleted 报错）
  }

  return {
    accounts,
    selectedAccountId,
    loadingAccounts,
    typeFilter,
    statusFilter,
    page,
    pageSize,
    logs,
    total,
    overview,
    loadingLogs,
    refreshingLogs,
    accountOptions,
    details,
    expandedId,
    detailOf,
    isOpen,
    toggleDetail,
    closeDetail,
    init,
    loadAccounts,
    loadLogs,
    selectAccount,
    setType,
    setStatus,
    setPage,
    setPageSize,
    removeLog,
    purgeBefore,
  }
})
