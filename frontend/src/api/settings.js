// 系统设置接口：管理员读写系统参数、系统信息；公开配置供未登录页使用
import request from '@/api/request'

// 设置项全量读取（仅管理员）：返回 { items: [{key,label,desc,type,current,default,min?,max?}] }
export function getSettings() {
  return request({ url: '/settings', method: 'get' })
}

// 批量保存设置（仅管理员）：{ settings: {key: value} }，返回更新后的 { items }
export function updateSettings(settings) {
  return request({ url: '/settings', method: 'put', data: { settings } })
}

// 公开配置（无需登录）：仅暴露展示型开关，当前为 { registration_enabled }
export function getPublicSettings() {
  return request({ url: '/settings/public', method: 'get' })
}

// 系统信息（仅管理员）：版本/环境/运行时长/数据库状态/用户统计
export function getSystemInfo() {
  return request({ url: '/system/info', method: 'get' })
}
