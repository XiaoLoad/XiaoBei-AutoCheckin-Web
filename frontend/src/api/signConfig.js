// 签到配置模块 API（/api/config-sets 与 /api/pools）。
// 视图形状沿用早期前端约定（system/user 双位置列表、sizeKb/inTrash、credentials.fields、
// uaTemplates.ua 等），由本适配层与后端领域形状互转。
// 任务实例与配置套的绑定（config_set_id）由 /api/schedules 提供，本文件不再持久化任务配置。
import request from '@/api/request'
import { bus, EVENTS } from '@/utils/eventBus'
import { fetchAccounts } from './accounts'

// 配置对象工厂：六类配置的默认骨架（值型随"配置套 → 任务实例"两层继承）
export function makeConfig() {
  return {
    time: {
      signTime: { hour: 8, minute: 0 }, // 定时签到时间（精确到时分）：调度器在每周选定星期、该时刻附近（叠加随机延时）触发；定时任务页默认采纳此时间
      startHour: 8, // 每日签到起始小时（业务时段：仅该时段内允许签到）
      endHour: 22, // 每日签到结束小时
      weekdays: [1, 2, 3, 4, 5, 6, 7], // 触发星期（1=周一 … 7=周日）多选
      randomDelayMax: 5, // 随机延时上限（分钟）
      mode: 'normal' // 签到模式：normal 普通 / holiday 节假日（运行时按年拉取第三方节假日接口）
    },
    locationId: null, // 引用型：所选位置 pool id（位置实体在位置池）
    fence: {
      intercept: true // 围栏拦截：提交前校验配置位置是否在任务围栏内，超出则不提交（防异常位置暴露）
    },
    remarks: [], // 值型：备注列表，每任务独立，后台随机取一条
    image: {
      enabled: false, // 是否上传图片
      strategy: 'recycle', // 图片策略：recycle 循环复用 / delete 用后删除 / trash 用后入回收站可恢复
      groupId: '' // 图片来源分组（'' = 全部图库）；同寝室账号选同一分组即共用照片
    },
    push: {
      channels: [], // 推送通道多选：serverchan / pushplus / email
      useOwnCredential: true, // true=回填"我的凭证"；false=下方直接填写
      credIds: { serverchan: null, pushplus: null, email: null }, // 回填"我的凭证"时各通道各自绑定的凭证 id
      cred: { serverchanKey: '', pushplusToken: '', emailSmtp: '', emailFrom: '', emailPass: '', emailTo: '' },
      notify: { success: true, skip: true, fail: true }, // 各状态推送开关：成功 / 跳过 / 失败
      template: 'html' // 推送模板：html（默认，优雅卡片）/ txt（纯文本）/ markdown
    },
    advanced: {
      uaTemplateId: null, // 引用型：所选 UA 模板 id（系统级资源池）
      customUa: '' // 自定义 UA（自由文本）
    }
  }
}

// ── 元信息：账号来自真实 /api/accounts ──
export async function fetchConfigMeta() {
  const accounts = await fetchAccounts()
  return {
    accounts: accounts.map((a) => ({
      id: String(a.id),
      name: (a.profile && a.profile.name) || a.account,
      studentNo: (a.profile && a.profile.studentNo) || '',
      className: (a.profile && a.profile.className) || '',
      platform: a.platform || 'B 打卡平台',
      status: a.enabled ? 'enabled' : 'disabled',
      signTasks: a.signTasks || []
    })),
    taskTypes: [
      { value: 'dorm', label: '寝室签到' },
      { value: 'activity', label: '活动签到' }
    ]
  }
}

// ── 用户配置套 ──
// config 垫上 makeConfig() 骨架（浅合并，已存字段优先）：启动种子/历史数据可能存在
// 空配置或仅含部分块的配置套，直接裸传会让 sections 读 config.time.startHour 等深层
// 字段时渲染崩溃（曾致整个签到配置 keep-alive 子树白屏，图库入口随之不可用）
const mapSetIn = (s) => ({
  id: String(s.id),
  name: s.name,
  isDefault: !!s.isDefault,
  // locationId 后端返回整数，前端选项值均为字符串；统一转字符串，避免 === 比对失败导致刷新后位置显示为空
  config: { ...makeConfig(), ...(s.config || {}), locationId: s.locationId != null ? String(s.locationId) : null }
})

export async function fetchConfigSets() {
  const data = await request({ url: '/config-sets', method: 'get' })
  const sets = (data.items || []).map(mapSetIn)
  return { userConfigSets: sets }
}

async function refreshSets() {
  const { userConfigSets } = await fetchConfigSets()
  return userConfigSets
}

export async function saveConfigSet(set) {
  const payload = { name: set.name, config: set.config }
  if (set.id) await request({ url: `/config-sets/${set.id}`, method: 'put', data: payload })
  else await request({ url: '/config-sets', method: 'post', data: payload })
  return refreshSets()
}

export async function deleteConfigSet(id) {
  await request({ url: `/config-sets/${id}`, method: 'delete' })
  return refreshSets()
}

// 应用全部：把当前配置套配置覆盖写入所有「已套用」该套的账号任务配置（需二次确认，后端执行）
// silent：store 层 catch 后用更贴身的文案提示，不走全局 toast
export async function applyConfigSetToAll(id) {
  const data = await request({ url: `/config-sets/${id}/apply-all`, method: 'post', silent: true })
  return data || {}
}

// ── 资源池 ──
const mapLocation = (l) => ({
  id: String(l.id), name: l.name, address: l.address || '',
  lat: l.lat, lng: l.lng, offset: l.offset ?? 10,
  enabled: l.enabled !== false, isSystem: !!l.isSystem
})

export async function fetchPools() {
  const p = await request({ url: '/pools', method: 'get' })
  const locations = (p.locations || []).map(mapLocation)
  const pools = {
    systemLocations: locations.filter((l) => l.isSystem),
    userLocations: locations.filter((l) => !l.isSystem),
    imageLibrary: (p.images || []).map((i) => ({ ...i })),
    imageGroups: (p.imageGroups || []).map((g) => ({ ...g })),
    credentials: (p.credentials || []).map((c) => ({ ...c, type: c.channel })),
    uaTemplates: (p.uas || []).map((u) => ({
      id: String(u.id), name: u.remark || '', ua: u.content, isSystem: !!u.isSystem
    }))
  }
  return pools
}

async function refreshPools() { return fetchPools() }

// 位置池：scope = system | user
export async function saveLocation(payload) {
  const body = {
    name: payload.name, address: payload.address || '',
    lat: Number(payload.lat), lng: Number(payload.lng),
    offset: Number(payload.offset) || 10, scope: payload.scope === 'system' ? 'system' : 'user'
  }
  if (payload.id) await request({ url: `/pools/locations/${payload.id}`, method: 'put', data: body })
  else await request({ url: '/pools/locations', method: 'post', data: body })
  const p = await refreshPools()
  return body.scope === 'system' ? p.systemLocations : p.userLocations
}

export async function deleteLocation(payload) {
  await request({ url: `/pools/locations/${payload.id}`, method: 'delete' })
  const p = await refreshPools()
  return payload.scope === 'system' ? p.systemLocations : p.userLocations
}

// UA 模板（管理员维护）
export async function saveUaTemplate(payload) {
  const body = { content: payload.ua, remark: payload.name || '' }
  if (payload.id) await request({ url: `/pools/uas/${payload.id}`, method: 'put', data: body })
  else await request({ url: '/pools/uas', method: 'post', data: body })
  return (await refreshPools()).uaTemplates
}
export async function deleteUaTemplate(id) {
  await request({ url: `/pools/uas/${id}`, method: 'delete' })
  return (await refreshPools()).uaTemplates
}
// 批量删除 UA 模板（管理员）：传入 id 数组，一次性移除
export async function deleteUaTemplates(ids) {
  await request({ url: '/pools/uas/bulk-delete', method: 'post', data: { ids } })
  return (await refreshPools()).uaTemplates
}

// 我的凭证（密文占位 •••• 原样回传，后端视为未修改保持旧值）
export async function saveCredential(payload) {
  const body = { channel: payload.type, name: payload.name, fields: payload.fields || {} }
  if (payload.id) await request({ url: `/pools/credentials/${payload.id}`, method: 'put', data: body })
  else await request({ url: '/pools/credentials', method: 'post', data: body })
  return (await refreshPools()).credentials
}
export async function deleteCredential(id) {
  await request({ url: `/pools/credentials/${id}`, method: 'delete' })
  return (await refreshPools()).credentials
}

// 测试推送：用该凭证真实发送一条样例消息，验证通道可用性（template 默认 html）
export async function testPushCredential(id, template = 'html') {
  await request({ url: `/pools/credentials/${id}/test-push`, method: 'post', data: { template } })
  return true
}

// 图库：真实上传（可指定分组）/ 回收站 / 删除
// onProgress 透传 axios 上传进度（0~100），用于拖拽/批量上传的进度展示
export async function uploadImage(file, groupId = null, onProgress, opts = {}) {
  const fd = new FormData()
  fd.append('file', file)
  if (groupId != null) fd.append('groupId', String(groupId))
  await request({
    url: '/pools/images', method: 'post', data: fd,
    headers: { 'Content-Type': 'multipart/form-data' }, timeout: 30000,
    silent: !!opts.silent,
    onUploadProgress: onProgress
      ? (e) => {
          const total = e.total || file.size || 0
          const percent = total ? Math.min(99, Math.round((e.loaded / total) * 100)) : 0
          onProgress(percent)
        }
      : undefined
  })
  return (await refreshPools()).imageLibrary
}
// 图库单图操作的 opts.silent：批量循环调用方传 true（批量面板自行汇总失败），
// 单图操作不传（失败由 request.js 全局 toast 兜底）
export async function trashImage(id, opts = {}) {
  await request({ url: `/pools/images/${id}/trash`, method: 'post', silent: !!opts.silent })
  return (await refreshPools()).imageLibrary
}
export async function restoreImage(id, opts = {}) {
  await request({ url: `/pools/images/${id}/restore`, method: 'post', silent: !!opts.silent })
  return (await refreshPools()).imageLibrary
}
export async function deleteImage(id, opts = {}) {
  await request({ url: `/pools/images/${id}`, method: 'delete', silent: !!opts.silent })
  return (await refreshPools()).imageLibrary
}
// 手动标记为已使用（图库页「标记已用」按钮；真实消费由调度器按 config.image.strategy 调后端 consume_image）
export async function markImageUsed(id, opts = {}) {
  await request({ url: `/pools/images/${id}/used`, method: 'post', silent: !!opts.silent })
  return (await refreshPools()).imageLibrary
}

// 图库分组（相册）：用户自建自管，名称通常为寝室号；同寝室账号共用同一分组
export async function createImageGroup(name) {
  await request({ url: '/pools/image-groups', method: 'post', data: { name } })
  return (await refreshPools()).imageGroups
}
export async function renameImageGroup(id, name) {
  await request({ url: `/pools/image-groups/${id}`, method: 'put', data: { name } })
  return (await refreshPools()).imageGroups
}
export async function deleteImageGroup(id) {
  await request({ url: `/pools/image-groups/${id}`, method: 'delete' })
  const p = await refreshPools()
  return { imageGroups: p.imageGroups, imageLibrary: p.imageLibrary }
}
export async function moveImageToGroup(id, groupId = null, opts = {}) {
  await request({
    url: `/pools/images/${id}/group`, method: 'put',
    data: { groupId: groupId == null ? null : Number(groupId) },
    silent: !!opts.silent
  })
  return (await refreshPools()).imageLibrary
}

// 缩略图 blob 拉取（<img> 无法带 Authorization 头；会话级缓存 objectURL）。
// 缓存生命周期：图片物理删除时释放对应 URL；登出时整体释放，杜绝 objectURL 只增不减的泄漏。
const blobCache = new Map()
export async function fetchImageBlobUrl(id) {
  if (blobCache.has(id)) return blobCache.get(id)
  const blob = await request({
    url: `/pools/images/${id}/file`, method: 'get',
    responseType: 'blob', timeout: 15000,
    // 文件丢失/网络失败时组件留占位图标即可，不逐图全局 toast
    silent: true
  })
  const url = URL.createObjectURL(blob)
  blobCache.set(id, url)
  return url
}

// 释放单张图片的 objectURL（图片记录已物理删除后调用；仍存在的图片不得调用，
// 否则其他组件的 <img> 会拿到已失效的 URL）
export function releaseImageBlob(id) {
  const url = blobCache.get(id)
  if (url) {
    URL.revokeObjectURL(url)
    blobCache.delete(id)
  }
}

// 释放全部 objectURL（登出时调用；与 request.js 的 AUTH_LOGOUT 订阅同一事件总线模式）
export function releaseAllImageBlobs() {
  for (const url of blobCache.values()) URL.revokeObjectURL(url)
  blobCache.clear()
}
bus.on(EVENTS.AUTH_LOGOUT, releaseAllImageBlobs)

// 任务实例与配置套的绑定（config_set_id）由 /api/schedules 提供；此处再导出供 signConfig store 复用
export { fetchScheduleBindings, createSchedule, deleteSchedule, updateSchedule } from './schedules'
