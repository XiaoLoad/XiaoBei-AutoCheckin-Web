// 签到配置领域状态（Pinia）：收纳用户配置套 / 任务实例配置 / 四类资源池的 mock 数据与 UI 状态。
// 后端接入时只需改 api/signConfig.js，本 store 与视图无需变动。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAuthStore } from '@/store/modules/auth'
import * as api from '@/api/signConfig'

export const useSignConfigStore = defineStore('signConfig', () => {
  const auth = useAuthStore()
  const isAdmin = computed(() => auth.isAdmin)

  const loading = ref(true)
  const saving = ref(false)

  // 元信息
  const accounts = ref([])
  const taskTypes = ref([
    { value: 'dorm', label: '寝室签到' },
    { value: 'activity', label: '活动签到' }
  ])

  // 用户配置套（多项命名模板）
  const userConfigSets = ref([])
  const activeSetId = ref('')

  // 任务实例配置：key = `${accountId}:${type}`
  const taskConfigs = ref({})

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
  const taskConfig = computed(() => taskConfigs.value[taskConfigKey.value] || null)

  // 账号树：账号 → 寝室/活动 两个任务节点
  const accountTree = computed(() =>
    accounts.value.map((a) => ({
      ...a,
      tasks: taskTypes.value.map((t) => ({
        accountId: a.id,
        type: t.value,
        label: t.label,
        key: `${a.id}:${t.value}`
      }))
    }))
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
  const setOptions = computed(() => userConfigSets.value.map((s) => ({ label: s.name, value: s.id })))

  function deepEqual(a, b) {
    if (a === b) return true
    if (typeof a !== 'object' || typeof b !== 'object' || a == null || b == null) return false
    const ka = Object.keys(a)
    const kb = Object.keys(b)
    if (ka.length !== kb.length) return false
    return ka.every((k) => deepEqual(a[k], b[k]))
  }

  // 任务状态：沿用某配置套 / 已修改 / 未关联
  const taskStatus = computed(() => {
    const cfg = taskConfig.value
    if (!cfg) return { text: '未选择任务', cls: 'bg-ink/10 text-ink-muted' }
    const id = cfg.presetSetId
    if (!id) return { text: '未关联配置套', cls: 'bg-ink/10 text-ink-muted' }
    const set = userConfigSets.value.find((s) => s.id === id)
    if (!set) return { text: '原配置套已删除', cls: 'bg-ink/10 text-ink-muted' }
    return deepEqual(cfg, set.config)
      ? { text: `沿用「${set.name}」`, cls: 'bg-info/10 text-info' }
      : { text: `已修改（基于「${set.name}」）`, cls: 'bg-amber/15 text-amber' }
  })

  // ── 加载 ──
  async function load() {
    loading.value = true
    try {
      const [meta, sets, pools] = await Promise.all([api.fetchConfigMeta(), api.fetchConfigSets(), api.fetchPools()])
      accounts.value = meta.accounts
      taskTypes.value = meta.taskTypes
      userConfigSets.value = sets.userConfigSets
      activeSetId.value = userConfigSets.value[0]?.id || ''
      systemLocations.value = pools.systemLocations
      userLocations.value = pools.userLocations
      imageLibrary.value = pools.imageLibrary
      credentials.value = pools.credentials
      uaTemplates.value = pools.uaTemplates

      // 预载所有任务实例配置（框架演示用；后端可改为按需加载）
      const entries = []
      for (const a of accounts.value) {
        for (const t of taskTypes.value) entries.push([`${a.id}:${t.value}`, api.fetchTaskConfig(a.id, t.value)])
      }
      const cfgs = await Promise.all(entries.map((e) => e[1]))
      const map = {}
      entries.forEach((e, i) => (map[e[0]] = cfgs[i]))
      taskConfigs.value = map

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
    saving.value = true
    try {
      const saved = await api.saveConfigSet({ id: activeSet.value.id, name: activeSet.value.name, config: activeSet.value.config })
      userConfigSets.value = saved
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
  async function saveTaskConfig() {
    if (!selectedAccountId.value) return
    saving.value = true
    try {
      const saved = await api.saveTaskConfig(selectedAccountId.value, selectedTaskType.value, taskConfig.value)
      taskConfigs.value = { ...taskConfigs.value, [taskConfigKey.value]: saved }
    } finally {
      saving.value = false
    }
  }
  // 从配置套回填到当前任务（引用哪一套配置进行回填）
  function applySetToTask(setId) {
    const set = userConfigSets.value.find((s) => s.id === setId)
    if (!set || !selectedAccountId.value) return
    const cloned = JSON.parse(JSON.stringify(set.config))
    cloned.presetSetId = set.id
    taskConfigs.value = { ...taskConfigs.value, [taskConfigKey.value]: cloned }
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
    activeSetId.value = id
  }
  function selectTask(accountId, type) {
    selectedAccountId.value = accountId
    selectedTaskType.value = type
  }

  return {
    loading,
    saving,
    accounts,
    taskTypes,
    userConfigSets,
    activeSetId,
    taskConfigs,
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
    accountTree,
    locationOptions,
    credentialOptions,
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
    saveLocation,
    deleteLocation,
    trashImage,
    restoreImage,
    deleteImage,
    saveCredential,
    deleteCredential,
    saveUaTemplate,
    deleteUaTemplate,
    deleteUaTemplates,
    setActiveTab,
    setResourceSubTab,
    gotoResource,
    setActiveSet,
    selectTask
  }
})
