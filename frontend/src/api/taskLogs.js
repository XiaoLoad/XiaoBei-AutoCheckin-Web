// 任务日志模块 API（对应后端 /api/tasks/logs）：
// 全局跨账号执行日志（sign_records 本地流水）。
// request 已统一给 URL 加 /api 前缀，故此处只写相对路径。
import request from '@/api/request'

// 后端 item → 前端契约：显式透传姓名/学院等字段，避免被归一化丢弃
function mapLog(it) {
  return {
    id: it.id,
    accountId: it.accountId,
    accountName: it.accountName || '',
    studentName: it.studentName || '',
    college: it.college || '',
    major: it.major || '',
    className: it.className || '',
    studentNo: it.studentNo || '',
    taskName: it.taskName || '',
    taskType: it.taskType || '',
    taskLabel: it.taskLabel || (it.taskType === 'dorm' ? '寝室签到' : '活动签到'),
    signDate: it.signDate || '',
    signedAt: it.signedAt || '',
    createdAt: it.createdAt || '',
    status: it.status || '',
    failReason: it.failReason || '',
    initiator: it.initiator || 'system',
  }
}

// 执行日志：返回 { items, total, page, pageSize, overview }
export async function fetchTaskLogs(params = {}) {
  const data = await request({ url: '/tasks/logs', method: 'get', params })
  const items = (data.items || []).map(mapLog)
  return {
    items,
    total: data.total || 0,
    page: data.page || 1,
    pageSize: data.pageSize || 10,
    overview: data.overview || { total: 0, success: 0, fail: 0, skip: 0 },
  }
}
