// 签到配置模块 API（前端框架阶段：返回 mock 数据，模拟网络延迟）。
// 后端就绪后，只需把下列函数体替换为对 request 的调用，store 与视图无需改动。
// 资源池（位置 / 图库 / 凭证）的增删改在 mock 层直接落库，便于前端联调演示。

const delay = (ms = 220) => new Promise((r) => setTimeout(r, ms))
const clone = (v) => JSON.parse(JSON.stringify(v))

// 配置对象工厂：六类配置的默认骨架（值型随"配置套 → 任务实例"两层继承）
export function makeConfig() {
  return {
    presetSetId: null, // 任务实例回填自哪个配置套（仅任务实例用，配置套内恒为 null）
    time: {
      startHour: 8, // 每日签到起始小时
      endHour: 22, // 每日签到结束小时
      weekdays: [1, 2, 3, 4, 5, 6, 7], // 触发星期（1=周一 … 7=周日）多选
      randomDelayMax: 5, // 随机延时上限（分钟）
      mode: 'normal' // 签到模式：normal 普通 / holiday 节假日（运行时按年拉取第三方节假日接口）
    },
    locationId: null, // 引用型：所选位置 pool id（位置实体在位置池）
    remarks: [], // 值型：备注列表，每任务独立，后台随机取一条
    image: {
      enabled: false, // 是否上传图片
      strategy: 'recycle' // 图片策略：recycle 循环复用 / delete 用后删除 / trash 用后入回收站可恢复
    },
    push: {
      channels: [], // 推送通道多选：serverchan / pushplus / email
      useOwnCredential: true, // true=回填"我的凭证"；false=下方直接填写
      credId: null, // 回填"我的凭证"时选中的凭证 id
      cred: { serverchanKey: '', pushplusToken: '', emailSmtp: '', emailFrom: '', emailPass: '', emailTo: '' },
      notify: { success: false, skip: true, fail: true } // 各状态推送开关：成功 / 跳过 / 失败
    },
    advanced: {
      uaTemplateId: null, // 引用型：所选 UA 模板 id（系统级资源池）
      customUa: '' // 自定义 UA（自由文本）
    }
  }
}

// 用指定星期生成一套配置（演示"不同批次时间不一致"的场景）
function setConfig(weekdays) {
  const c = makeConfig()
  c.time.weekdays = weekdays
  return c
}

// ── mock 数据源（仅前端框架演示，后端接入后删除） ──
const mock = {
  accounts: [
    { id: 'acc1', name: '张三 / 寝室号A101', platform: 'B平台', status: 'enabled' },
    { id: 'acc2', name: '李四 / 寝室号B202', platform: 'B平台', status: 'enabled' },
    { id: 'acc3', name: '王五 / 寝室号C303', platform: 'B平台', status: 'disabled' },
    { id: 'acc4', name: '赵六 / 寝室号D404', platform: 'B平台', status: 'enabled' },
    { id: 'acc5', name: '钱七 / 寝室号E505', platform: 'B平台', status: 'enabled' },
    { id: 'acc6', name: '孙八 / 寝室号F606', platform: 'B平台', status: 'enabled' },
    { id: 'acc7', name: '周九 / 寝室号G707', platform: 'B平台', status: 'disabled' },
    { id: 'acc8', name: '吴十 / 寝室号H808', platform: 'B平台', status: 'enabled' },
    { id: 'acc9', name: '郑十一 / 寝室号I909', platform: 'B平台', status: 'enabled' },
    { id: 'acc10', name: '王十二 / 寝室号J010', platform: 'B平台', status: 'enabled' },
    { id: 'acc11', name: '李十三 / 寝室号K111', platform: 'B平台', status: 'enabled' },
    { id: 'acc12', name: '刘十四 / 寝室号L212', platform: 'B平台', status: 'disabled' }
  ],
  taskTypes: [
    { value: 'dorm', label: '寝室签到' },
    { value: 'activity', label: '活动签到' }
  ],
  // 用户配置套（多项命名模板）：不同 B 账号批次时间规律不同，分别建套
  userConfigSets: [
    { id: 'set_std', name: '标准套（周一至周日）', config: setConfig([1, 2, 3, 4, 5, 6, 7]) },
    { id: 'set_wed_fri', name: '周三至周五', config: setConfig([3, 4, 5]) },
    { id: 'set_sun', name: '仅周日', config: setConfig([7]) }
  ],
  taskConfigs: {}, // key: `${accountId}:${type}`
  systemLocations: [
    { id: 'sloc1', name: '校东门', address: 'https://map.example.com/east', lat: 30.1234, lng: 120.4567, offset: 50 },
    { id: 'sloc2', name: '图书馆正门', address: 'https://map.example.com/lib', lat: 30.1241, lng: 120.4578, offset: 30 }
  ],
  userLocations: [
    { id: 'uloc1', name: '我的寝室', address: 'https://map.example.com/dorm', lat: 30.1255, lng: 120.4589, offset: 20 }
  ],
  imageLibrary: [
    { id: 'img1', name: '签到图1.jpg', sizeKb: 182, inTrash: false },
    { id: 'img2', name: '签到图2.jpg', sizeKb: 156, inTrash: false }
  ],
  credentials: [
    { id: 'cred1', name: 'Server酱-主力', type: 'serverchan', fields: { serverchanKey: 'SCTxxxx' } },
    { id: 'cred2', name: 'PushPlus-备用', type: 'pushplus', fields: { pushplusToken: 'tokenxxxx' } },
    { id: 'cred3', name: '邮箱-通知', type: 'email', fields: { emailSmtp: 'smtp.example.com', emailFrom: 'a@example.com', emailPass: '******', emailTo: 'b@example.com' } }
  ],
  uaTemplates: [
    { id: 'ua1', name: 'iPhone 15', ua: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148' },
    { id: 'ua2', name: '小米 14', ua: 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Mobile' },
    { id: 'ua3', name: '华为 Mate 60', ua: 'Mozilla/5.0 (Linux; Android 14; HUAWEI ALN-AL00) AppleWebKit/537.36 Chrome/120 Mobile' }
  ]
}

// 预生成任务实例配置：以首个配置套为起点（新建即套用），记录 presetSetId
const firstSet = mock.userConfigSets[0]
for (const a of mock.accounts) {
  for (const t of mock.taskTypes) {
    const cfg = clone(firstSet.config)
    cfg.presetSetId = firstSet.id
    mock.taskConfigs[`${a.id}:${t.value}`] = cfg
  }
}

// ── 元信息 ──
export async function fetchConfigMeta() {
  await delay()
  return clone({ accounts: mock.accounts, taskTypes: mock.taskTypes })
}

// ── 用户配置套（多项命名模板） ──
export async function fetchConfigSets() {
  await delay()
  return clone({ userConfigSets: mock.userConfigSets })
}
export async function saveConfigSet(set) {
  await delay()
  if (set.id) {
    const i = mock.userConfigSets.findIndex((s) => s.id === set.id)
    if (i !== -1) mock.userConfigSets[i] = clone(set)
  } else {
    mock.userConfigSets.push({ id: `set_${Date.now()}`, ...clone(set) })
  }
  return clone(mock.userConfigSets)
}
export async function deleteConfigSet(id) {
  await delay()
  return clone((mock.userConfigSets = mock.userConfigSets.filter((s) => s.id !== id)))
}

// ── 任务实例配置 ──
export async function fetchTaskConfig(accountId, type) {
  await delay()
  return clone(mock.taskConfigs[`${accountId}:${type}`])
}
export async function saveTaskConfig(accountId, type, config) {
  await delay()
  mock.taskConfigs[`${accountId}:${type}`] = clone(config)
  return clone(mock.taskConfigs[`${accountId}:${type}`])
}

// ── 资源池 ──
export async function fetchPools() {
  await delay()
  return clone({
    systemLocations: mock.systemLocations,
    userLocations: mock.userLocations,
    imageLibrary: mock.imageLibrary,
    credentials: mock.credentials,
    uaTemplates: mock.uaTemplates
  })
}

// 位置池：scope = system | user
export async function saveLocation(payload) {
  await delay()
  const arr = payload.scope === 'system' ? mock.systemLocations : mock.userLocations
  if (payload.id) {
    const i = arr.findIndex((x) => x.id === payload.id)
    if (i !== -1) arr[i] = { ...arr[i], ...payload }
  } else {
    arr.push({ id: `loc_${Date.now()}`, ...payload })
  }
  return clone(arr)
}
export async function deleteLocation(payload) {
  await delay()
  const arr = payload.scope === 'system' ? mock.systemLocations : mock.userLocations
  return clone((mock[payload.scope === 'system' ? 'systemLocations' : 'userLocations'] = arr.filter((x) => x.id !== payload.id)))
}

// UA 模板（系统级，管理员维护）
export async function saveUaTemplate(payload) {
  await delay()
  if (payload.id) {
    const i = mock.uaTemplates.findIndex((x) => x.id === payload.id)
    if (i !== -1) mock.uaTemplates[i] = { ...mock.uaTemplates[i], ...payload }
  } else {
    mock.uaTemplates.push({ id: `ua_${Date.now()}`, name: payload.name, ua: payload.ua })
  }
  return clone(mock.uaTemplates)
}
export async function deleteUaTemplate(id) {
  await delay()
  return clone((mock.uaTemplates = mock.uaTemplates.filter((x) => x.id !== id)))
}

// 图库：上传（模拟）、删除（移入回收站）、恢复
export async function saveImage(payload) {
  await delay()
  if (payload.id) {
    const i = mock.imageLibrary.findIndex((x) => x.id === payload.id)
    if (i !== -1) mock.imageLibrary[i] = { ...mock.imageLibrary[i], ...payload }
  } else {
    mock.imageLibrary.push({ id: `img_${Date.now()}`, sizeKb: 0, inTrash: false, ...payload })
  }
  return clone(mock.imageLibrary)
}
export async function trashImage(id) {
  await delay()
  const it = mock.imageLibrary.find((x) => x.id === id)
  if (it) it.inTrash = true
  return clone(mock.imageLibrary)
}
export async function restoreImage(id) {
  await delay()
  const it = mock.imageLibrary.find((x) => x.id === id)
  if (it) it.inTrash = false
  return clone(mock.imageLibrary)
}
export async function deleteImage(id) {
  await delay()
  return clone((mock.imageLibrary = mock.imageLibrary.filter((x) => x.id !== id)))
}

// 我的凭证
export async function saveCredential(payload) {
  await delay()
  if (payload.id) {
    const i = mock.credentials.findIndex((x) => x.id === payload.id)
    if (i !== -1) mock.credentials[i] = { ...mock.credentials[i], ...payload }
  } else {
    mock.credentials.push({ id: `cred_${Date.now()}`, ...payload })
  }
  return clone(mock.credentials)
}
export async function deleteCredential(id) {
  await delay()
  return clone((mock.credentials = mock.credentials.filter((x) => x.id !== id)))
}
