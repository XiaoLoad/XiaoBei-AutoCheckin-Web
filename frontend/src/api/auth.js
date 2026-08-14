// 鉴权相关接口
import request from '@/api/request'

// 登录：入参 { account, password }，返回 { token, user_id, username, role }
export function login(data) {
  return request.post('/auth/login', data)
}

// 获取当前登录用户信息（需携带 token）
export function getMe() {
  return request.get('/auth/me')
}

// 注销：吊销当前 token（服务端黑名单），返回 {}
export function logout() {
  return request.post('/auth/logout')
}
