// 全站签到记录接口（管理员巡检）：数据与用户端「签到记录页」同源——B 平台历史任务
// 经后端代理读取，前端不持有任何 B 平台凭据 / token。后端契约见 admin.py 的
// /api/admin/site-records/*（admin_required 鉴权，admin 可读任意账号）。
//
//   GET /api/admin/site-records/tree
//       全站用户 → B 平台账号 两级树；账号为 BAccount.to_dict 契约形状
//   GET /api/admin/site-records/accounts/:id/records?type=&status=&date_from=&date_to=&page=&page_size=
//       历史签到任务分页；返回 { items, total, page, page_size, overview, meta }
//   GET /api/admin/site-records/accounts/:id/records/:taskId/detail?kind=know|sign
//       任务地理围栏 + 签到记录列表；返回 { geoFence, logs }
import request from '@/api/request'

export async function fetchSiteTree() {
  const data = await request({ url: '/admin/site-records/tree', method: 'get' })
  return { items: data.items || [], total: data.total || 0 }
}

export async function fetchAccountHistory(
  accountId,
  { type = 'all', status = 'all', page = 1, pageSize = 10, dateFrom, dateTo } = {}
) {
  if (!accountId) {
    return { items: [], total: 0, page: 1, page_size: pageSize, overview: null, meta: null }
  }
  const params = { type, status, page, page_size: pageSize }
  if (dateFrom) params.date_from = dateFrom
  if (dateTo) params.date_to = dateTo
  const data = await request({
    url: `/admin/site-records/accounts/${accountId}/records`,
    method: 'get',
    params,
  })
  return {
    items: data.items || [],
    total: data.total || 0,
    page: data.page || page,
    page_size: data.page_size || pageSize,
    overview: data.overview || null,
    meta: data.meta || null,
  }
}

export async function fetchAccountTaskDetail(accountId, taskId, kind = 'know') {
  if (!accountId || !taskId) return { geoFence: [], logs: [] }
  const data = await request({
    url: `/admin/site-records/accounts/${accountId}/records/${taskId}/detail`,
    method: 'get',
    params: { kind },
  })
  return { geoFence: data.geoFence || [], logs: data.logs || [] }
}

// 管理员受限回显指定账号的 B 平台密码：登录密码二次验证 + 服务端限流，
// 每次查看（含密码错误）后端都会落一条 account.secret_view 审计。
// 明文只在本次响应里存在，前端不得写入任何持久化状态。
export function revealAccountSecret(accountId, loginPassword) {
  return request({
    url: `/admin/accounts/${accountId}/secret`,
    method: 'post',
    data: { login_password: loginPassword },
  })
}
