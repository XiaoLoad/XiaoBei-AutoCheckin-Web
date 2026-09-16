// 用户日志（平台操作审计）接口：对应后端 /api/op-logs（仅管理员可访问）。
// request 已统一给 URL 加 /api 前缀，故此处只写相对路径。
import request from '@/api/request'

// 后端 event → 前端契约：显式透传，避免被归一化丢弃 detail 这类可选块
function mapEvent(it) {
  return {
    id: it.id,
    time: it.time || '',
    createdAt: it.createdAt || '',
    action: it.action || '',
    category: it.category || '',
    result: it.result || 'success',
    summary: it.summary || '',
    detail: it.detail || null,
    ip: it.ip || '',
  }
}

// 后端 item → 前端契约：平铺流水行
function mapLog(it) {
  return {
    id: it.id,
    userId: it.userId,
    username: it.username || '',
    role: it.role || '',
    action: it.action || '',
    category: it.category || '',
    result: it.result || 'success',
    summary: it.summary || '',
    detail: it.detail || null,
    ip: it.ip || '',
    userAgent: it.userAgent || '',
    createdAt: it.createdAt || '',
  }
}

// 会话段 → 前端契约
function mapSession(it) {
  return {
    id: it.id,
    userId: it.userId,
    username: it.username || '',
    role: it.role || '',
    ip: it.ip || '',
    startAt: it.startAt || '',
    endAt: it.endAt || '',
    startTime: it.startTime || '',
    durationSeconds: it.durationSeconds || 0,
    running: !!it.running,
    closeReason: it.closeReason || 'orphan',
    eventCount: it.eventCount || 0,
    events: (it.events || []).map(mapEvent),
  }
}

// 平铺流水：params = { page, page_size, category, result, action, username, keyword, date_from, date_to }
export async function fetchOpLogs(params = {}) {
  const data = await request({ url: '/op-logs', method: 'get', params })
  return {
    items: (data.items || []).map(mapLog),
    total: data.total || 0,
    page: data.page || 1,
    pageSize: data.page_size || 20,
  }
}

// 会话段列表：过滤参数与流水完全一致
export async function fetchOpLogSessions(params = {}) {
  const data = await request({ url: '/op-logs/sessions', method: 'get', params })
  return {
    items: (data.items || []).map(mapSession),
    total: data.total || 0,
    page: data.page || 1,
    pageSize: data.page_size || 10,
  }
}

// 页头指标 + 异常聚合 + 保留天数（指标恒为「今日」口径，不随筛选变化）
export async function fetchOpLogSummary() {
  const data = await request({ url: '/op-logs/summary', method: 'get' })
  return {
    metrics: data.metrics || {
      loginToday: 0, loginFailToday: 0, userChangeToday: 0, ongoingSessions: 0,
    },
    anomalies: data.anomalies || [],
    anomalyWindowDays: data.anomalyWindowDays || 7,
    retentionDays: data.retentionDays || 365,
  }
}

// 筛选项：分类与动作的现存值（带计数）
export async function fetchOpLogMeta() {
  const data = await request({ url: '/op-logs/meta', method: 'get' })
  return {
    categories: data.categories || [],
    actions: data.actions || [],
  }
}
