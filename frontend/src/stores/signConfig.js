// 签到配置领域状态（Pinia）：收纳用户配置套 / 任务实例配置 / 四类资源池的 mock 数据与 UI 状态。
// 后端接入时只需改 api/signConfig.js，本 store 与视图无需变动。
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'
import * as api from '@/api/signConfig'

export const useSignConfigStore = defineStore('signConfig', () => {
  const auth = useAuthStore()
  const isAdmin = computed(() => auth.isAdmin)

  const loading = ref(true)
  const saving = ref(false)

  // 必填校验错误：键为 time / location / remarks，值为提示文案；保存前若非空则阻断提交
  const formErrors = ref({})

  // 校验一份配置是否满足必填：时间配置 / 位置配置 / 备注列表 三项为必填
  function validateConfig(config) {
    const errors = {}
    const t = config.time || {}
    const sh = Number(t.startHour)
    const eh = Number(t.endHour)
    if (t.startHour == null || t.endHour == null || Number.isNaN(sh) || Number.isNaN(eh)) {
      errors.time = '请设置完整的签到时间段'
    } else if (sh >= eh) {
      errors.time = '开始时间须早于结束时间'
    } else if (!Array.isArray(t.weekdays) || t.weekdays.length === 0) {
      errors.time = '请至少选择一个触发星期'
    }
    if (!config.locationId) errors.location = '请选择签到位置'
    const validRemarks = (config.remarks || []).filter((r) => String(r ?? '').trim() !== '')
    if (validRemarks.length === 0) errors.remarks = '请至少填写一条备注'
    return errors
  }
  function clearFormErrors() {
    formErrors.value = {}
  }
  // 当前正在编辑的配置对象：任务页编辑 taskConfig，其余页编辑默认配置套
  function currentEditableConfig() {
    if (activeTab.value === 'tasks') return taskConfig.value
    return activeSet.value?.config
  }
  // 实时消除：某必填项被填写后，立即从 formErrors 移除该项（无需再次提交）。
  // 只删、不增——仅当该项当前已不再非法时才清除，避免误清未填项。
  function liveClearErrors() {
    const errs = formErrors.value
    if (!errs || Object.keys(errs).length === 0) return
    const cfg = currentEditableConfig()
    if (!cfg) return
    const stillInvalid = validateConfig(cfg)
    const next = {}
    for (const k of Object.keys(errs)) {
      if (stillInvalid[k]) next[k] = errs[k]
    }
    formErrors.value = next
  }

  // 元信息
  const accounts = ref([])
  const taskTypes = ref([
    { value: 'dorm', label: '寝室签到' },
    { value: 'activity', label: '活动签到' }
  ])

  // 用户配置套（多项命名模板）
  const userConfigSets = ref([])
  const activeSetId = ref('')

  // 任务实例与配置套的绑定：key = `${accountId}:${type}` → { scheduleId, configSetId, enabled }
  // configSetId 为 null 表示未绑定（localStorage 不再存任务配置，见模块 C）
  const scheduleBindings = ref({})

  // 配置套「已保存快照」：configSetId → 深拷贝的配置，用于判断当前编辑是否脏（有无未保存改动）。
  // 仅比对当前任务所绑定配置套的内容，因此共享同一配置套的多任务互不干扰。
  const savedSnapshots = ref({})
  function snapshotSets() {
    const map = {}
    for (const s of userConfigSets.value) map[s.id] = JSON.parse(JSON.stringify(s.config))
    savedSnapshots.value = map
  }
  function refreshSnapshot(id) {
    const s = userConfigSets.value.find((x) => x.id === id)
    if (!s) return
    savedSnapshots.value = { ...savedSnapshots.value, [s.id]: JSON.parse(JSON.stringify(s.config)) }
  }

  // 资源池
  const systemLocations = ref([])
  const userLocations = ref([])
  const imageLibrary = ref([])
  const credentials = ref([])
  const uaTemplates = ref([])

  // UI 状态
  const activeTab = ref('default') // default(配置套) | tasks | resources
  const resourceSubTab = ref('locations') // locations | images | credentials | ua
  const selectedAccountId = ref('')
  const selectedTaskType = ref('dorm')

  // ── 计算：当前配置套 / 任务配置对象 ──
  const activeSet = computed(
    () => userConfigSets.value.find((s) => s.id === activeSetId.value) || userConfigSets.value[0] || null
  )
  const taskConfigKey = computed(() => `${selectedAccountId.value}:${selectedTaskType.value}`)
  // 用户默认配置套（is_default 优先，否则取列表首个）：未绑定任务的下拉默认值与预览来源
  const defaultSetId = computed(() => {
    const d = userConfigSets.value.find((s) => s.isDefault)
    if (d) return d.id
    return userConfigSets.value[0]?.id || ''
  })
  // 当前任务绑定的配置套 id（来自后端 Schedule.config_set_id）
  const boundSetId = computed(() => {
    const b = scheduleBindings.value[taskConfigKey.value]
    return b && b.configSetId ? b.configSetId : null
  })
  // 任务配置即其跟随配置套的配置（follow 模型）：
  // 已绑定 → 绑定套配置；未绑定 → 默认套配置（预览），点「应用到此任务」后才真正落库绑定
  const taskConfig = computed(() => {
    const setId = boundSetId.value
    const set = setId ? userConfigSets.value.find((s) => s.id === setId) : null
    const src = set || userConfigSets.value.find((s) => s.isDefault) || userConfigSets.value[0] || null
    return src ? src.config : null
  })

  // 当前编辑对象所隶属的配置套 id：已绑定则用绑定套，未绑定则回退默认配置套。
  // 未绑定时 taskConfig 即默认套配置，编辑它本质就是在改默认套，脏检测同样应生效。
  const activeConfigSetId = computed(() => boundSetId.value || defaultSetId.value)
  // 当前任务「是否脏」：当前显示配置相对其所属配置套的已保存快照有改动时为 true。
  // 用于：保存按钮是否可点（无改动禁用）、添加至定时任务是否放行（未保存禁止推送）。
  const isDirty = computed(() => {
    const setId = activeConfigSetId.value
    const cfg = taskConfig.value
    if (!setId || !cfg) return false
    const snap = savedSnapshots.value[setId]
    if (!snap) return false
    return JSON.stringify(cfg) !== JSON.stringify(snap)
  })

  // 当前账号×类型的调度实例状态：是否已创建实例 / 是否启用 / 实例与绑定 id
  const taskScheduleState = computed(() => {
    const b = scheduleBindings.value[taskConfigKey.value]
    return {
      hasInstance: !!(b && b.scheduleId),
      enabled: !!(b && b.enabled),
      scheduleId: b ? b.scheduleId : null,
      configSetId: b ? b.configSetId : null
    }
  })

  // 账号树：账号 → 寝室/活动 两个任务节点；节点 enabled 基于该账号已添加至定时任务且启用的签到类型
  const accountTree = computed(() =>
    accounts.value.map((a) => {
      const st = a.signTasks || []
      return {
        ...a,
        tasks: taskTypes.value.map((t) => {
          const node = st.find((s) => s.type === t.value)
          return {
            accountId: a.id,
            type: t.value,
            label: t.label,
            key: `${a.id}:${t.value}`,
            enabled: !!(node && node.enabled)
          }
        })
      }
    })
  )

  // 引用型配置的可选项（带来源前缀，便于在 BaseSelect 中区分系统/用户资源）
  const locationOptions = computed(() => {
    const sys = systemLocations.value.map((l) => ({ label: `系统 · ${l.name}`, value: l.id }))
    const mine = userLocations.value.map((l) => ({ label: `我的 · ${l.name}`, value: l.id }))
    return [{ label: '不指定位置', value: '' }, ...sys, ...mine]
  })
  const credentialOptions = computed(() => credentials.value.map((c) => ({ label: `${c.name}（${c.type}）`, value: c.id })))
  const uaOptions = computed(() => [{ label: '自定义 UA', value: '' }, ...uaTemplates.value.map((u) => ({ label: u.name, value: u.id }))])
  const channelOptions = [
    { label: 'Server酱', value: 'serverchan' },
    { label: 'PushPlus', value: 'pushplus' },
    { label: '邮件', value: 'email' }
  ]
  // 按通道类型分组的凭证选项：推送配置里每个通道各自绑定一个凭证，只能选同类型的
  const credentialOptionsByChannel = computed(() => {
    const map = {}
    for (const c of channelOptions) {
      map[c.value] = [
        { label: '未选择', value: '' },
        ...credentials.value.filter((x) => x.type === c.value).map((x) => ({ label: x.name, value: x.id }))
      ]
    }
    return map
  })
  const setOptions = computed(() => userConfigSets.value.map((s) => ({ label: s.name, value: s.id })))

  // 任务状态：沿用某配置套 / 未关联（follow 模型下任务配置即配置套配置，无独立修改态）
  const taskStatus = computed(() => {
    const b = scheduleBindings.value[taskConfigKey.value]
    if (!b || !b.configSetId) return { text: '未关联配置套', cls: 'bg-ink/10 text-ink-muted' }
    const set = userConfigSets.value.find((s) => s.id === b.configSetId)
    if (!set) return { text: '原配置套已删除', cls: 'bg-ink/10 text-ink-muted' }
    return { text: `沿用「${set.name}」`, cls: 'bg-info/10 text-info' }
  })

  // 供定时任务页「跟随配置套」预览：解析某任务绑定配置套的时间/位置元信息
  function taskConfigMetaOf(accountId, type) {
    const key = `${accountId}:${type}`
    const b = scheduleBindings.value[key]
    const setId = b ? b.configSetId : null
    const set = setId ? userConfigSets.value.find((s) => s.id === setId) : null
    const cfg = set ? set.config : null
    if (!cfg) return { time: null, presetSetName: '未关联', locationName: '未设置位置' }
    const loc =
      userLocations.value.find((l) => l.id === cfg.locationId) ||
      systemLocations.value.find((l) => l.id === cfg.locationId)
    return {
      time: cfg.time ? JSON.parse(JSON.stringify(cfg.time)) : null,
      presetSetName: set ? set.name : '未关联',
      locationName: loc ? loc.name : '未设置位置'
    }
  }

  // ── 加载 ──
  async function load() {
    loading.value = true
    try {
      const [meta, sets, pools] = await Promise.all([api.fetchConfigMeta(), api.fetchConfigSets(), api.fetchPools()])
      accounts.value = meta.accounts
      taskTypes.value = meta.taskTypes
      userConfigSets.value = sets.userConfigSets
      snapshotSets()
      activeSetId.value = userConfigSets.value[0]?.id || ''
      systemLocations.value = pools.systemLocations
      userLocations.value = pools.userLocations
      imageLibrary.value = pools.imageLibrary
      credentials.value = pools.credentials
      uaTemplates.value = pools.uaTemplates

      // 任务实例与配置套的绑定（config_set_id）来自后端 schedules；本地不再持久化任务配置
      try {
        scheduleBindings.value = await api.fetchScheduleBindings()
      } catch (e) {
        scheduleBindings.value = {}
      }

      if (accounts.value.length) {
        selectedAccountId.value = accounts.value[0].id
        selectedTaskType.value = 'dorm'
      }
    } finally {
      loading.value = false
    }
  }

  // ── 配置套：增删改 ──
  async function saveActiveSet() {
    if (!activeSet.value) return
    const errs = validateConfig(activeSet.value.config)
    if (Object.keys(errs).length) {
      formErrors.value = errs
      toast(`保存失败：${Object.values(errs).join('；')}`, 'error')
      return
    }
    formErrors.value = {}
    saving.value = true
    try {
      const saved = await api.saveConfigSet({ id: activeSet.value.id, name: activeSet.value.name, config: activeSet.value.config })
      userConfigSets.value = saved
      refreshSnapshot(activeSet.value.id)
    } finally {
      saving.value = false
    }
  }
  async function createConfigSet(name) {
    saving.value = true
    try {
      const saved = await api.saveConfigSet({ name: name || `配置套 ${userConfigSets.value.length + 1}`, config: api.makeConfig() })
      userConfigSets.value = saved
      activeSetId.value = saved[saved.length - 1].id
    } finally {
      saving.value = false
    }
  }
  async function deleteConfigSet(id) {
    saving.value = true
    try {
      const saved = await api.deleteConfigSet(id)
      userConfigSets.value = saved
      if (activeSetId.value === id) activeSetId.value = saved[0]?.id || ''
    } finally {
      saving.value = false
    }
  }
  async function renameConfigSet(id, name) {
    const set = userConfigSets.value.find((s) => s.id === id)
    if (!set) return
    set.name = name
    saving.value = true
    try {
      const saved = await api.saveConfigSet({ id: set.id, name: set.name, config: set.config })
      userConfigSets.value = saved
    } finally {
      saving.value = false
    }
  }

  // ── 任务实例配置保存 ──
  // 任务配置即配置套配置（follow 模型）：保存即写回「当前编辑所隶属的配置套」
  // （已绑定用绑定套，未绑定用默认套）。若任务已启用定时，调用方会先弹出覆盖确认。
  async function saveTaskConfig() {
    if (!selectedAccountId.value) return
    const setId = boundSetId.value || defaultSetId.value
    if (!setId) {
      toast('暂无可用配置套，无法保存', 'error')
      return
    }
    const set = userConfigSets.value.find((s) => s.id === setId)
    if (!set) return
    const errs = validateConfig(set.config)
    if (Object.keys(errs).length) {
      formErrors.value = errs
      toast(`保存失败：${Object.values(errs).join('；')}`, 'error')
      return
    }
    formErrors.value = {}
    saving.value = true
    try {
      const saved = await api.saveConfigSet({ id: set.id, name: set.name, config: set.config })
      userConfigSets.value = saved
      refreshSnapshot(set.id)
      toast('配置已保存到配置套', 'success')
    } finally {
      saving.value = false
    }
  }
  // 将某配置套应用到当前任务：若调度实例尚不存在则先创建（幂等），再写入 config_set_id（后端自动置 mode=follow）。
  // 这样「用户添加账号 → 选配置套回填 → 保存推送」即可创建定时任务，无需先建实例。
  async function applySetToTask(setId) {
    const setIdStr = String(setId)
    const set = userConfigSets.value.find((s) => s.id === setIdStr)
    if (!set || !selectedAccountId.value) return
    const key = taskConfigKey.value
    const b = scheduleBindings.value[key]
    saving.value = true
    try {
      let scheduleId = b && b.scheduleId
      if (!scheduleId) {
        const created = await api.createSchedule({ accountId: Number(selectedAccountId.value), taskType: selectedTaskType.value })
        scheduleId = created.id
      }
      // 套用即推送：绑定配置套（后端自动置 follow）并立即启用，使其生效（语义与"添加至定时任务"一致）
      await api.updateSchedule({ id: scheduleId, enabled: true, configSetId: Number(setIdStr) })
      scheduleBindings.value = {
        ...scheduleBindings.value,
        [key]: { scheduleId, configSetId: setIdStr, enabled: true }
      }
      toast('已套用配置并推送至定时任务（已启用）', 'success')
    } catch (e) {
      toast(e.message || '应用配置套失败', 'error')
    } finally {
      saving.value = false
    }
  }

  // 清空当前正在编辑的配置（舍弃所有已填内容，回到默认空白模板）。
  // 配合「保存按钮旁的清空填写」使用：Tab 切换内容由 store 持有不会丢失，此为手动显式清空。
  function resetActiveSetConfig() {
    const i = userConfigSets.value.findIndex((s) => s.id === activeSetId.value)
    if (i === -1) return
    const clone = { ...userConfigSets.value[i] }
    clone.config = api.makeConfig()
    userConfigSets.value[i] = clone
    formErrors.value = {}
  }
  // 放弃未保存修改：重新拉取配置套（任务配置即配置套配置，无独立任务副本）
  async function resetTaskConfig() {
    if (!selectedAccountId.value) return
    saving.value = true
    try {
      userConfigSets.value = (await api.fetchConfigSets()).userConfigSets
      snapshotSets()
      formErrors.value = {}
    } finally {
      saving.value = false
    }
  }

  // ── 资源池：位置 ──
  async function saveLocation(payload) {
    saving.value = true
    try {
      const arr = await api.saveLocation(payload)
      if (payload.scope === 'system') systemLocations.value = arr
      else userLocations.value = arr
    } finally {
      saving.value = false
    }
  }
  async function deleteLocation(payload) {
    saving.value = true
    try {
      const arr = await api.deleteLocation(payload)
      if (payload.scope === 'system') systemLocations.value = arr
      else userLocations.value = arr
    } finally {
      saving.value = false
    }
  }

  // ── 资源池：图库 ──
  async function trashImage(id) {
    saving.value = true
    try {
      imageLibrary.value = await api.trashImage(id)
    } finally {
      saving.value = false
    }
  }
  async function restoreImage(id) {
    saving.value = true
    try {
      imageLibrary.value = await api.restoreImage(id)
    } finally {
      saving.value = false
    }
  }
  async function deleteImage(id) {
    saving.value = true
    try {
      imageLibrary.value = await api.deleteImage(id)
    } finally {
      saving.value = false
    }
  }
  // 上传图片：走真实归一化管线，成功后刷新图库数组
  async function uploadImage(file) {
    saving.value = true
    try {
      imageLibrary.value = await api.uploadImage(file)
    } finally {
      saving.value = false
    }
  }

  // ── 资源池：凭证 ──
  async function saveCredential(payload) {
    saving.value = true
    try {
      credentials.value = await api.saveCredential(payload)
    } finally {
      saving.value = false
    }
  }
  async function deleteCredential(id) {
    saving.value = true
    try {
      credentials.value = await api.deleteCredential(id)
    } finally {
      saving.value = false
    }
  }

  // ── 资源池：UA 模板（系统级，管理员维护） ──
  async function saveUaTemplate(payload) {
    saving.value = true
    try {
      uaTemplates.value = await api.saveUaTemplate(payload)
    } finally {
      saving.value = false
    }
  }
  async function deleteUaTemplate(id) {
    saving.value = true
    try {
      uaTemplates.value = await api.deleteUaTemplate(id)
    } finally {
      saving.value = false
    }
  }
  async function deleteUaTemplates(ids) {
    saving.value = true
    try {
      uaTemplates.value = await api.deleteUaTemplates(ids)
    } finally {
      saving.value = false
    }
  }

  // ── UI 切换 ──
  function setActiveTab(tab) {
    activeTab.value = tab
  }
  function setResourceSubTab(sub) {
    resourceSubTab.value = sub
  }
  // 从配置项里的「管理」入口跳转到「我的资源 / 系统资源」指定子页
  function gotoResource(sub) {
    resourceSubTab.value = sub
    activeTab.value = 'resources'
  }
  function setActiveSet(id) {
    if (activeSetId.value !== id) formErrors.value = {}
    activeSetId.value = id
  }
  function selectTask(accountId, type) {
    if (selectedAccountId.value !== accountId || selectedTaskType.value !== type) formErrors.value = {}
    selectedAccountId.value = accountId
    selectedTaskType.value = type
  }

  // 监听必填字段内容：一旦变化且该项已合法，立刻清掉对应红框/提醒。
  // 放在此处（activeTab / taskConfig 等已初始化之后）注册，避免 watch getter 同步取值时触发 TDZ。
  watch(
    () => {
      const cfg = currentEditableConfig()
      if (!cfg) return null
      const t = cfg.time || {}
      return {
        time: JSON.stringify({ sh: t.startHour, eh: t.endHour, wd: t.weekdays }),
        loc: cfg.locationId,
        rem: JSON.stringify((cfg.remarks || []).map((r) => String(r ?? '').trim()))
      }
    },
    () => liveClearErrors(),
    { deep: false }
  )

  return {
    loading,
    saving,
    formErrors,
    accounts,
    taskTypes,
    userConfigSets,
    activeSetId,
    scheduleBindings,
    defaultSetId,
    systemLocations,
    userLocations,
    imageLibrary,
    credentials,
    uaTemplates,
    activeTab,
    resourceSubTab,
    selectedAccountId,
    selectedTaskType,
    activeSet,
    taskConfigKey,
    taskConfig,
    taskStatus,
    taskConfigMetaOf,
    isDirty,
    taskScheduleState,
    accountTree,
    locationOptions,
    credentialOptions,
    credentialOptionsByChannel,
    uaOptions,
    channelOptions,
    setOptions,
    load,
    saveActiveSet,
    createConfigSet,
    deleteConfigSet,
    renameConfigSet,
    saveTaskConfig,
    applySetToTask,
    resetActiveSetConfig,
    resetTaskConfig,
    saveLocation,
    deleteLocation,
    trashImage,
    restoreImage,
    deleteImage,
    uploadImage,
    saveCredential,
    deleteCredential,
    saveUaTemplate,
    deleteUaTemplate,
    deleteUaTemplates,
    setActiveTab,
    setResourceSubTab,
    gotoResource,
    setActiveSet,
    selectTask,
    validateConfig,
    clearFormErrors
  }
})
