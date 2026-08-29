// 个人中心聚合 API（对应后端 /api/me/overview）：普通用户仪表盘数据源。
// request 已统一给 URL 加 /api 前缀，故此处只写相对路径。
import request from '@/api/request'

// 后端 overview → 前端原样透传；空数据时给稳定默认值，避免图表/统计卡拿到 undefined。
export async function fetchOverview() {
  const data = await request({ url: '/me/overview', method: 'get' })
  return {
    quota: data.quota || { used: 0, limit: 0, pct: 0 },
    accounts: data.accounts || { total: 0, items: [] },
    tasks: data.tasks || { total: 0, active: 0 },
    today: data.today || { total: 0, success: 0, fail: 0, skip: 0 },
    trend: data.trend || { '7d': [], '30d': [] },
    typeDist: data.typeDist || { dorm: 0, activity: 0 },
    taskSummary: data.taskSummary || { success: 0, fail: 0, skip: 0 },
    recentLogs: data.recentLogs || [],
  }
}
