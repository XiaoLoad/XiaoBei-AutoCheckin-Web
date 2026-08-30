// 任务日志领域状态（Pinia）：编排全局跨账号执行日志（sign_records 本地流水）。
// 账号列表复用 accounts API，供执行日志筛选器使用。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchAccounts } from '@/api/accounts'
import { fetchTaskLogs, deleteTaskLog, purgeTaskLogs } from '@/api/taskLogs'

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
    await purgeTaskLogs({ before, accountId, type, status })
    page.value = 1
    await loadLogs()
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
