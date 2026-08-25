// B 平台账号管理接口（已接真后端 /api/accounts）
// 数据形状见 @/api/types 中的 Account（前后端契约），store 与业务组件零改动。
// 预检（preflight）不落库：实时走 B 平台登录链路，成功后缓存 profile，
// 供表单在「校验通过 → 提交前」的 fetchProfile 回填预览使用。
import request from '@/api/request'

let lastPreflight = { account: '', profile: null }

export async function fetchAccounts(params = {}) {
  const data = await request({ url: '/accounts', method: 'get', params })
  return data.items || []
}

export async function createAccount(payload) {
  return request({ url: '/accounts', method: 'post', data: payload })
}

export async function updateAccount(id, payload) {
  return request({ url: `/accounts/${id}`, method: 'put', data: payload })
}

export async function deleteAccount(id) {
  await request({ url: `/accounts/${id}`, method: 'delete' })
  return true
}

// 凭据预检：后端实时校验 B 平台账密；失败时 request 拦截器抛错（message 为后端文案）
export async function verifyAccount(account, password) {
  const data = await request({
    url: '/accounts/preflight', method: 'post', data: { account, password },
  })
  lastPreflight = { account, profile: data.profile || null }
  return { ok: !!data.ok, message: data.message || '校验通过' }
}

// 表单预览回填：复用最近一次预检成功的 profile（组件总是在 verify 通过后调用本函数）
export async function fetchProfile(account) {
  if (lastPreflight.account === account && lastPreflight.profile) {
    return lastPreflight.profile
  }
  return { name: '', college: '', major: '', className: '', studentNo: '' }
}
