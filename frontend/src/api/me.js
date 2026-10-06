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
    scheduler: data.scheduler || {
      running: false, jobCount: 0, unregistered: 0,
      taskTypes: { dorm: 0, activity: 0 },
      lastRunAt: '', lastRunAgo: '', nextRunIn: null, nextRuns: [],
    },
    pushHealth: data.pushHealth || {
      days: 7,
      summary: { sent: 0, ok: 0, fail: 0, skipped: 0, rate: null, channels: 0 },
      byChannel: [], signOkPushFail: { total: 0, list: [] },
    },
  }
}

// 个人设置页「账户信息」只读卡（对应后端 /api/me/account-info）。
// 空值兜底为稳定默认值，避免骨架屏结束后渲染出 undefined。
export async function fetchAccountInfo() {
  const data = await request({ url: '/me/account-info', method: 'get' })
  return {
    userId: data.userId ?? null,
    username: data.username || '',
    role: data.role || 'user',
    createdAt: data.createdAt || '',
    lastLogin: data.lastLogin || '',
    quota: data.quota || { used: 0, limit: 0, pct: 0 },
  }
}
