// 鉴权相关接口
import request from '@/api/request'

// 登录：入参 { account, password }，返回 { token, user_id, username, role }
// silent：登录页自行 alert 展示失败原因，不走全局 toast
export function login(data) {
  return request.post('/auth/login', data, { silent: true })
}

// 注销：吊销当前 token（服务端黑名单），返回 {}
export function logout() {
  return request.post('/auth/logout')
}

// 修改当前登录用户密码：{ old_password, new_password }
export function changePassword(data) {
  return request.put('/auth/password', data)
}
