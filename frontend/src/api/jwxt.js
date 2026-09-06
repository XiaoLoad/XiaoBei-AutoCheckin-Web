// 教务系统对接 API（/api/b-accounts/:id/jwxt）：绑定、同步、概览与当日窗口。
// 绑定/同步为**异步任务**：接口只落库/入队立即返回（亚秒级），真正的教务拉取在后台
// 串行队列执行；前端凭概览里的 syncRunning 轮询直到完成，结果看 account.status/lastError。
// 概览返回 { bound, account, semester, courses, windows, timetableSyncedAt, syncRunning }。
import request from '@/api/request'

export async function fetchJwxtOverview(accountId, date = null) {
  const query = date ? `?date=${date}` : ''
  const data = await request({ url: `/b-accounts/${accountId}/jwxt${query}`, method: 'get', silent: true })
  return data || { bound: false, windows: [] }
}

export async function bindJwxt(accountId, { studentNo, password }) {
  const data = await request({
    url: `/b-accounts/${accountId}/jwxt`, method: 'post',
    data: { studentNo, password }, timeout: 15000
  })
  return data || {}
}

export async function syncJwxt(accountId) {
  const data = await request({ url: `/b-accounts/${accountId}/jwxt/sync`, method: 'post', timeout: 15000 })
  return data || {}
}

export async function unbindJwxt(accountId) {
  await request({ url: `/b-accounts/${accountId}/jwxt`, method: 'delete' })
  return true
}
