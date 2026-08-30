// 管理员仪表盘领域状态（Pinia）：对接 /api/admin/overview 聚合端点。
// 沿用 SWR 纪律：loading 仅首次加载（骨架屏），此后静默刷新（视图降透明 + RefreshStrip）。
// 日志区筛选（type/username/page）随 overview 一并传参，后端仅作用于日志区，
// 筛选同时会静默刷新其它区块（顺带换新，无额外代价）。
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchAdminOverview } from '@/api/admin'

const EMPTY = {
  summary: {
    users: 0, activeUsers30d: 0, accounts: 0, accountsEnabled: 0,
    quota: { used: 0, total: 0, pct: 0 },
    today: { success: 0, fail: 0, skip: 0, total: 0 },
  },
  trend: { '7d': [], '30d': [] },
  failCategories: [],
  quota: { buckets: { unused: 0, lt50: 0, r50to79: 0, r80to99: 0, full: 0 },
           warnRatio: 80, warnTotal: 0, warnUsers: [] },
  riskUsers: [],
  accountHealth: {
    invalidCredentials: { total: 0, list: [] },
    staleSign: { total: 0, list: [] },
  },
  scheduler: { running: false, jobCount: 0, todayRuns: 0, nextRuns: [] },
  recentLogs: { items: [], total: 0, page: 1, page_size: 10 },
  schedulesEnabled: 0,
}

export const useAdminOverviewStore = defineStore('adminOverview', () => {
  const data = ref(JSON.parse(JSON.stringify(EMPTY)))
  const loading = ref(false)
  const refreshing = ref(false)
  const loaded = ref(false)
  // 全局日志筛选：type(dorm|activity) / username(模糊) / page
  const logFilters = ref({ type: 'all', username: '', page: 1 })
  let seq = 0

  async function loadOverview(filters) {
    if (filters) logFilters.value = { ...logFilters.value, ...filters }
    const first = !loaded.value
    if (first) loading.value = true
    else refreshing.value = true
    const my = ++seq
    const f = logFilters.value
    const params = {}
    if (f.type && f.type !== 'all') params.type = f.type
    if (f.username) params.username = f.username
    if (f.page > 1) params.page = f.page
    try {
      const res = await fetchAdminOverview(params)
      if (my !== seq) return // 竞态守卫：仅采纳最新请求
      data.value = res
      loaded.value = true
    } finally {
      if (my === seq) {
        loading.value = false
        refreshing.value = false
      }
    }
  }

  // 日志筛选变更：页码归一为 1（除非显式传 page）
  function setLogFilters(filters) {
    return loadOverview({ page: 1, ...filters })
  }

  return { data, loading, refreshing, loaded, logFilters, loadOverview, setLogFilters }
})
