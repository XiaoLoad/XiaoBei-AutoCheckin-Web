// 仪表盘领域状态（Pinia）：对接 /api/me/overview，聚合当前用户的配额/账号/任务/日志概览。
// 纯只读；loading 态驱动统计卡与图表的骨架占位。
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchOverview } from '@/api/me'

const EMPTY = {
  quota: { used: 0, limit: 0, pct: 0 },
  accounts: { total: 0, items: [] },
  tasks: { total: 0, active: 0 },
  today: { total: 0, success: 0, fail: 0, skip: 0 },
  trend: { '7d': [], '30d': [] },
  typeDist: { dorm: 0, activity: 0 },
  taskSummary: { success: 0, fail: 0, skip: 0 },
  recentLogs: [],
}

export const useDashboardStore = defineStore('dashboard', () => {
  const overview = ref({ ...EMPTY })
  const loading = ref(false)
  const loaded = ref(false)

  async function loadOverview() {
    loading.value = true
    try {
      overview.value = await fetchOverview()
      loaded.value = true
    } catch (e) {
      overview.value = { ...EMPTY }
    } finally {
      loading.value = false
    }
  }

  return { overview, loading, loaded, loadOverview }
})
