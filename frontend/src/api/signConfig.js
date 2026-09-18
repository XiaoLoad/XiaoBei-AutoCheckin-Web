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
      // 取图方式：fixed 固定图库（全部账号共用 groupId 指向的库）/ byGroup 按分组取图
      // （各账号按所属分组的图库归属取图，适合一个配置套覆盖多寝室）
      mode: 'fixed',
      groupKind: 'dorm', // byGroup 时按哪类分组取图：dorm 寝室分组 / class 班级分组
      groupId: '' // 固定图库分组（'' = 全部图库）；byGroup 时作为分组未绑图库的回退默认值
    },
    push: {
      channels: [], // 推送通道多选：serverchan / pushplus / email
      useOwnCredential: true, // true=回填"我的凭证"；false=下方直接填写
      // true=各账号自带凭证（按执行账号取其在账号管理里绑定的凭证）；false=用套级凭证。
      // 默认 false：老配置套语义不变，且账号未绑凭证时不会把原有推送静默掐掉。
      useAccountCredential: false,
      credIds: { serverchan: null, pushplus: null, email: null }, // 回填"我的凭证"时各通道各自绑定的凭证 id
      cred: { serverchanKey: '', pushplusToken: '', emailSmtp: '', emailFrom: '', emailPass: '', emailTo: '' }, // emailTo 可多个，逗号分隔
      notify: { success: true, skip: true, fail: true }, // 各状态推送开关：成功 / 跳过 / 失败
      template: 'html' // 推送模板：html（默认，优雅卡片）/ txt（纯文本）/ markdown
    },
    advanced: {
      uaTemplateId: null, // 引用型：所选 UA 模板 id（系统级资源池）
      customUa: '' // 自定义 UA（自由文本）
    },
    activity: {
      // 活动签到专属（寝室签到任务不消费此块）：fixed=沿用上方时间配置每天一次查询；
      // course=按教务课表展开的当日时间窗内低频轮询（无课日零查询）
      strategy: 'fixed',
      course: {
        leadMinutes: 60, // 时段开始前 60 分钟开始留意（辅导员最早提前 50 分钟发布，实测数据）
        tailMinutes: 30, // 课程结束后延续 30 分钟关窗（覆盖拖堂/课间发布）
        pollIntervalSec: 120, // 窗口内查询 B 平台的间隔（秒）
        excludeCourses: [], // 课程名黑名单（如毕业实习不参与轮询）
        weekdays: [] // 限定星期（空 = 不限，1=周一…7=周日）
      },
      fallback: {
        enabled: true // 每日按上方 signTime 兜底查询一次（覆盖无节次课程与临时活动）
      }
    }
  }
}

// activity 块骨架兜底：历史/脏数据可能只有 {strategy:...} 甚至空对象，模板深绑定
// config.activity.course.* 会直接崩。无条件补齐 course/fallback 内层对象与默认值，
// 返回同一引用（就地修复，保持响应式）。
export function ensureActivityConfig(activity) {
  if (!activity || typeof activity !== 'object') return activity
  const full = makeConfig().activity
  const course = activity.course && typeof activity.course === 'object' ? activity.course : {}
  activity.course = { ...full.course, ...course }
  const fallback = activity.fallback && typeof activity.fallback === 'object' ? activity.fallback : {}
  activity.fallback = { ...full.fallback, ...fallback }
  if (!activity.strategy) activity.strategy = 'fixed'
  return activity
}

// image 块骨架兜底：mode/groupKind 是后加的键，历史配置套与任务快照里都没有；
// 缺键会让取图方式下拉显示空白、并让 configsEqual 把历史快照误判为「已偏离配置套」。
// 与 ensureActivityConfig 同理就地补齐，返回同一引用（保持响应式）。
export function ensureImageConfig(image) {
  if (!image || typeof image !== 'object') return image
  image.mode = image.mode === 'byGroup' ? 'byGroup' : 'fixed'
  image.groupKind = image.groupKind === 'class' ? 'class' : 'dorm'
  if (!image.strategy) image.strategy = makeConfig().image.strategy
  return image
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
      signTasks: a.signTasks || [],
      // 账号自带的推送凭证绑定 {channel: credentialId}：配置套推送来源选「各账号自带」时按此取凭证
      pushCreds: a.pushCreds || {}
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
// 配置套已按适用类型分类（taskType: dorm 寝室 / activity 活动，创建后锁定）：
// 寝室套编辑器不含活动调度卡片；绑定/批量应用按类型一一对应
const mapSetIn = (s) => {
  const config = { ...makeConfig(), ...(s.config || {}) }
  ensureActivityConfig(config.activity)
  ensureImageConfig(config.image)
  return {
    id: String(s.id),
    name: s.name,
    isDefault: !!s.isDefault,
    taskType: s.taskType === 'activity' ? 'activity' : 'dorm',
    // locationId 后端返回整数，前端选项值均为字符串；统一转字符串，避免 === 比对失败导致刷新后位置显示为空
    config: { ...config, locationId: s.locationId != null ? String(s.locationId) : null }
  }
}

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
  const payload = { name: set.name, config: set.config, taskType: set.taskType || 'dorm' }
  if (set.id) await request({ url: `/config-sets/${set.id}`, method: 'put', data: payload })
  else await request({ url: `/config-sets`, method: 'post', data: payload })
  return refreshSets()
}

export async function deleteConfigSet(id) {
  await request({ url: `/config-sets/${id}`, method: 'delete' })
  return refreshSets()
}

// 批量应用：把配置套配置快照套用到指定账号任务（targets: [{accountId, taskType}]）。
// silent：store 层 catch 后用更贴身的文案提示，不走全局 toast
export async function applyConfigSetBatch(id, targets) {
  const data = await request({ url: `/config-sets/${id}/apply-batch`, method: 'post', data: { targets }, silent: true })
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

// 凭证单拉：账号推送绑定这类只需要凭证列表的场景用，避免连带拉取图库等全量资源池
export async function fetchCredentials() {
  const data = await request({ url: '/pools/credentials', method: 'get' })
  return (data.items || []).map((c) => ({ ...c, type: c.channel }))
}

// 图库分组单拉：分组页绑定图库归属这类只需要分组列表的场景用，避免连带拉取图库等全量资源池
export async function fetchImageGroups() {
  const data = await request({ url: '/pools/image-groups', method: 'get' })
  return (data.items || []).map((g) => ({
    id: String(g.id), name: g.name, count: g.count || 0
  }))
}

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

// 新建单条凭证：回传新建记录本身（含 id），供「绑定处就地新建」直接并入本地选项，
// 不必为一条新凭证把整个资源池重拉一遍（saveCredential 走的是全量刷新）
export async function createCredential(payload) {
  const data = await request({
    url: '/pools/credentials', method: 'post',
    data: { channel: payload.type, name: payload.name, fields: payload.fields || {} }
  })
  return { ...data, type: data.channel }
}

// 测试推送：用该凭证真实发送一条样例消息，验证通道可用性（template 默认 html）。
// qqCode 仅 pushplus-open（QQ 群）通道使用：选填，留空发本人、填了发群。
export async function testPushCredential(id, template = 'html', qqCode = '') {
  await request({
    url: `/pools/credentials/${id}/test-push`,
    method: 'post',
    data: { template, qqCode: qqCode || '' },
  })
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
