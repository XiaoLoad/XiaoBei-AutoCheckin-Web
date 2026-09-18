// 分组接口（班级按 className 派生 / 寝室手动成员），对应后端 /api/group-push。
// 分组同时承载 QQ 群（合并推送）与图库归属（配置套「按分组取图」），两者各自独立可空。
import request from '@/api/request'

// 列出分组：type=class 返回账号 className 实时派生项；type=dorm 返回显式建的行
export async function fetchGroups(type) {
  const data = await request({ url: '/group-push/groups', method: 'get', params: { type } })
  return data.items || []
}

// 新建寝室分组（payload: name / qqCode / imageGroupId）
export async function createDormGroup(payload) {
  return request({ url: '/group-push/groups', method: 'post', data: payload })
}

// 编辑寝室分组（name / qqCode / imageGroupId，传哪个改哪个）
export async function updateDormGroup(id, payload) {
  return request({ url: `/group-push/groups/${id}`, method: 'put', data: payload })
}

// 删除寝室分组
export async function deleteDormGroup(id) {
  await request({ url: `/group-push/groups/${id}`, method: 'delete' })
  return true
}

// 列出寝室分组成员
export async function fetchMembers(id) {
  const data = await request({ url: `/group-push/groups/${id}/members`, method: 'get' })
  return data.items || []
}

// 寝室分组成员地图（全部组一次取回）：accountId → 所属分组。
// 账号卡片要标注所属寝室分组，而账号列表接口不带这层归属；按分组逐个取成员会在
// 账号页产生 N+1，故由后端一次 join 返回。
export async function fetchDormMembers() {
  const data = await request({ url: '/group-push/dorm-members', method: 'get' })
  return data.items || []
}

// 批量添加成员
export async function addMembers(id, accountIds) {
  return request({ url: `/group-push/groups/${id}/members`, method: 'post', data: { accountIds } })
}

// 移除单个成员
export async function removeMember(id, accountId) {
  await request({ url: `/group-push/groups/${id}/members/${accountId}`, method: 'delete' })
  return true
}

// 班级分组保存（name 必填；qqCode / imageGroupId 传哪个改哪个，两者皆空则整行解绑删除）
export async function bindClassGroup(payload) {
  return request({ url: '/group-push/class-bind', method: 'post', data: payload })
}

// 手动立即汇总发送（测试 / 补发）
export async function flushGroup(payload) {
  return request({ url: '/group-push/flush', method: 'post', data: payload })
}
