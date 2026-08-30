// 管理员仪表盘 API：单聚合端点返回全部区块数据（全站汇总/趋势/失败归类/额度分桶/
// 高频失败/账号健康/调度器/全局日志），聚合 SQL 全部在后端下推。
// recentLogs 的筛选参数（type/username/page）随 overview 一并传递，后端仅作用于日志区。
import request from '@/api/request'

export function fetchAdminOverview(params = {}) {
  return request({ url: '/admin/overview', method: 'get', params })
}
