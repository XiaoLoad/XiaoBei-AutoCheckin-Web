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

// 删除单条执行日志（仅本人归属，后端校验）
export async function deleteTaskLog(id) {
  return request({ url: `/tasks/logs/${id}`, method: 'delete' })
}

// 批量删除本人执行日志：必须带 before（YYYY-MM-DD），清理该日期之前的全部记录；
// accountId/type/status 可选叠加过滤。后端无 before 直接 400 拒绝。
export async function purgeTaskLogs({ before, accountId, type, status } = {}) {
  const params = {}
  if (before) params.before = before
  if (accountId) params.accountId = accountId
  if (type && type !== 'all') params.type = type
  if (status && status !== 'all') params.status = status
  return request({ url: '/tasks/logs', method: 'delete', params })
}
