// 仪表盘领域状态（Pinia）：对接 /api/me/overview，聚合当前用户的配额/账号/任务/日志概览。
// 纯只读；loading 态驱动统计卡与图表的骨架占位。
import { defineStore } from 'pinia'
import { useRefreshBusStore } from '@/stores/refreshBus'
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
  const refreshBus = useRefreshBusStore()
  const overview = ref({ ...EMPTY })
  const loading = ref(false)
  const loaded = ref(false)
  // 无感刷新：再次进入仪表盘时旧数据原地保留（统计卡/图表原地换数），仅标记刷新态供视图降透明
  const refreshing = ref(false)

  // seq 竞态守卫：并发两次调用时仅采纳最新响应，先结束者不得覆盖新数据
  // 或提前复位 loading/refreshing（与 adminOverview.js 同款模式）
  let seq = 0

  async function loadOverview() {
    const first = !loaded.value
    if (first) loading.value = true
    else {
      refreshing.value = true
      refreshBus.begin()
    }
    const my = ++seq
    try {
      const data = await fetchOverview()
      if (my !== seq) return // 竞态守卫：仅采纳最新请求
      overview.value = data
      loaded.value = true
    } catch (e) {
      if (my !== seq) return
      // 失败时保留旧数据（首次失败才落回空态骨架），避免刷新把已渲染内容打空
      if (!loaded.value) overview.value = { ...EMPTY }
    } finally {
      // 总线计数按调用配对回落（被淘汰的请求也登记过 begin）
      if (!first) refreshBus.end()
      if (my === seq) {
        loading.value = false
        refreshing.value = false
      }
    }
  }

  return { overview, loading, refreshing, loaded, loadOverview }
})
