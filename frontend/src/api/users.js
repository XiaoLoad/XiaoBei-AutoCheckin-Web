// 用户管理接口：列表（分页/过滤）、新增、编辑、禁用启用、删除（桩）
// 返回结构见 @/api/types 中的 UserListResult / UserListItem（前后端契约）
import request from '@/api/request'

// 用户列表：支持分页、关键词、角色过滤
// params: { page, page_size, keyword, role }
export function getUsers(params) {
  return request({ url: '/users', method: 'get', params })
}

// 新增用户：{ username, password, role, enabled, quota }
export function createUser(data) {
  return request({ url: '/users', method: 'post', data })
}

// 编辑用户：{ username?, password?, role?, enabled?, quota? }
export function updateUser(id, data) {
  return request({ url: `/users/${id}`, method: 'put', data })
}

// 禁用 / 启用：{ enabled }
export function setUserStatus(id, enabled) {
  return request({ url: `/users/${id}/status`, method: 'patch', data: { enabled } })
}

// 删除用户：当前后端为桩接口，暂不实际删除
export function deleteUser(id) {
  return request({ url: `/users/${id}`, method: 'delete' })
}
