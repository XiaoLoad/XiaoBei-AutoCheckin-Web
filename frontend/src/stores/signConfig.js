// 签到配置领域状态（Pinia）：收纳用户配置套 / 任务实例配置 / 四类资源池的真实后端数据
// 与 UI 状态。接口细节见 api/signConfig.js，本 store 只做编排与本地派生。
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { toast } from '@/utils/toast'
import * as api from '@/api/signConfig'

export const useSignConfigStore = defineStore('signConfig', () => {
  const loading = ref(true)
  // 无感刷新：首次加载显示骨架屏；再次进入页面（store 已有缓存）后台静默换新
  const refreshing = ref(false)
  const loaded = ref(false)
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
  // 资源可用性兜底：配置引用的位置 / 图片必须真实存在于对应资源池，否则提示补全。
  // 用于「保存配置套」「启用 / 保存任务配置」前，防止位置池或图库被清空后仍能保存或启动。
  // 失效的旧位置引用在此直接置空，避免把悬空 id 落库。
  function validateResources(config) {
    const errs = {}
    const loc = config.locationId
    if (loc) {
      const exists = systemLocations.value.some((l) => l.id === loc) ||
        userLocations.value.some((l) => l.id === loc)
      if (!exists) {
        config.locationId = '' // 旧引用已失效，置空等待用户重新选择
        errs.location = '原选位置已不存在（位置池可能已清空），请重新选择'
      }
    }
    const hasLocationPool = systemLocations.value.length > 0 || userLocations.value.length > 0
    if (!hasLocationPool && !config.locationId) {
      errs.location = errs.location || '位置池暂无数据，请先到「我的资源 → 位置池」添加签到位置'
    }
    const img = config.image || {}
    if (img.enabled && imageLibrary.value.filter((i) => !i.inTrash).length === 0) {
      errs.image = '已开启图片签到但图库暂无图片，请先到「我的资源 → 图库」上传'
    }
    return errs
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
  const imageGroups = ref([])
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
  // 任务自持配置草稿：账号任务配置界面编辑的是「本任务配置」的副本，
  // 保存时写回任务实例并解绑配置套（快照复制模型），绝不直接改共享配置套。
  const taskConfigDraft = ref(null)
  const draftSourceSnapshot = ref(null)
  // 比对两份配置是否实质一致。
  // [规范化] ① 骨架垫底：缺失的可选块（如 fence 之前的历史快照）与默认值视为一致，
  //          避免骨架演进导致历史快照被误判"已不一致"；
  //         ② 递归按键名排序：配置 JSON 的顶层/内层键序随写入路径不同（实测存在
  //          makeConfig 序与字母序两种），JSON 原文比较对键序敏感会误判，故先规范化。
  // 位置 id 统一按字符串归一（来源套经 mapSetIn 转字符串，任务快照可能为字符串或数字）。
  function canonicalize(v) {
    if (Array.isArray(v)) return v.map(canonicalize)
    if (v && typeof v === 'object') {
      const out = {}
      for (const k of Object.keys(v).sort()) out[k] = canonicalize(v[k])
      return out
    }
    return v
  }
  function configsEqual(a, b) {
    if (a === b) return true
    if (!a || !b) return false
    const norm = (c) => JSON.stringify(
      canonicalize({ ...api.makeConfig(), ...(c || {}), locationId: c?.locationId == null ? null : String(c.locationId) })
    )
    return norm(a) === norm(b)
  }
  function initTaskDraft() {
    const key = taskConfigKey.value
    const b = scheduleBindings.value[key]
    let src = null
    if (b && b.config) {
      src = b.config                         // 任务已自持配置（套用/保存后）
    } else {
      const setId = effectiveBindSetId.value
      const set = userConfigSets.value.find((s) => s.id === setId)
      src = set ? set.config : null          // 仍跟随：预览绑定/所选套（只读源）
    }
    taskConfigDraft.value = src ? JSON.parse(JSON.stringify(src)) : null
    draftSourceSnapshot.value = src ? JSON.parse(JSON.stringify(src)) : null
  }
  // 任务配置即当前编辑草稿（深拷贝自来源，修改仅作用于本任务，不影响共享配置套）
  const taskConfig = computed(() => taskConfigDraft.value)

  // 当前任务「是否脏」：草稿相对来源快照有改动时为 true（保存按钮可点 / 启用前校验）。
  const isDirty = computed(() => {
    const cfg = taskConfigDraft.value
    if (!cfg) return false
    const snap = draftSourceSnapshot.value
    if (!snap) return true
    return JSON.stringify(cfg) !== JSON.stringify(snap)
  })
  // 当前正在编辑的配置套相对其「已保存快照」是否脏：未改动时禁用「保存配置套」按钮。
  const activeSetDirty = computed(() => {
    const s = activeSet.value
    if (!s) return false
    const snap = savedSnapshots.value[s.id]
    if (!snap) return true
    return JSON.stringify(s.config) !== JSON.stringify(snap)
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
    // 三方平台签到位置为必填，不指定属错误状态，故下拉不提供「不指定位置」清空项
    return [...sys, ...mine]
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
      // 凭证为必填项，不提供「未选择」清空项，避免勾选通道却不绑凭证的悬挂状态
      map[c.value] = credentials.value.filter((x) => x.type === c.value).map((x) => ({ label: x.name, value: x.id }))
    }
    return map
  })
  const setOptions = computed(() => userConfigSets.value.map((s) => ({ label: s.name, value: s.id })))

  // 任务状态：自持配置且解绑 / 自持配置且保留源自标签 / 仍跟随配置套 / 未关联
  const taskStatus = computed(() => {
    const b = scheduleBindings.value[taskConfigKey.value]
    if (b && b.config) {
      if (b.configSetId) {
        const set = userConfigSets.value.find((s) => s.id === b.configSetId)
        if (!set) return { text: '原配置套已删除（自定义配置）', cls: 'bg-warning/10 text-warning' }
        // 任务配置快照与当前配置套内容比对：一致=仍沿用；不一致=来源已改，视为自定义
        if (configsEqual(b.config, set.config)) {
          return { text: `已套用「${set.name}」`, cls: 'bg-info/10 text-info' }
        }
        return { text: '自定义配置（与配置套已不一致）', cls: 'bg-warning/10 text-warning' }
      }
      return { text: '自定义配置（已解绑配置套）', cls: 'bg-info/10 text-info' }
    }
    if (b && b.configSetId) {
      const set = userConfigSets.value.find((s) => s.id === b.configSetId)
      if (!set) return { text: '原配置套已删除', cls: 'bg-ink/10 text-ink-muted' }
      return { text: `沿用「${set.name}」`, cls: 'bg-info/10 text-info' }
    }
    return { text: '未关联配置套', cls: 'bg-ink/10 text-ink-muted' }
  })
  // 任务自持配置是否已与「来源配置套」当前内容一致（对齐）：仅 b.config && b.configSetId 时有意义。
  // 用于「套用」按钮禁用判定——同一配置套且已对齐时，套用是纯空操作，禁用；
  // 一旦配置套被改（任务漂移为「自定义」）则放开，点击套用即把最新配置覆盖回任务、重新对齐。
  const taskAlignedWithSource = computed(() => {
    const b = scheduleBindings.value[taskConfigKey.value]
    if (!b || !b.config || !b.configSetId) return false
    const set = userConfigSets.value.find((s) => s.id === b.configSetId)
    if (!set) return false
    return configsEqual(b.config, set.config)
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
    const first = !loaded.value
    if (first) loading.value = true
    else refreshing.value = true
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
      imageGroups.value = pools.imageGroups || []
      credentials.value = pools.credentials
      uaTemplates.value = pools.uaTemplates

      // 任务实例绑定（config_set_id / config / 运行信息）来自后端 schedules；本地不再持久化任务配置
      await refreshBindings()
      initTaskDraft()

      if (accounts.value.length) {
        // 保留当前选择（若仍存在），仅在选择失效时回落到首个账号——避免刷新动作打断用户所在位置
        const stillThere = accounts.value.some((a) => a.id === selectedAccountId.value)
        if (!stillThere) {
          selectedAccountId.value = accounts.value[0].id
          selectedTaskType.value = 'dorm'
        }
      }
      loaded.value = true
    } finally {
      loading.value = false
      refreshing.value = false
    }
  }

  // 轻量刷新：仅重拉任务绑定（启用/暂停/换绑/覆盖变更后调用），不重置用户当前选择
  async function refreshBindings() {
    try {
      scheduleBindings.value = await api.fetchScheduleBindings()
    } catch (e) {
      scheduleBindings.value = {}
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
    const resErrs = validateResources(activeSet.value.config)
    if (Object.keys(resErrs).length) {
      formErrors.value = { ...formErrors.value, ...resErrs }
      toast(`保存失败：${Object.values(resErrs).join('；')}`, 'error')
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

  // ── 账号任务配置（A 方案语义）：选套编辑 / 启用 / 暂停 / 换绑 ──
  // 未绑定任务的本地选套：下拉选择即以该套为编辑目标；点「启用定时任务」时创建实例并绑定它
  const selectedBindSetId = ref('')
  // 实际生效的编辑目标：优先下拉所选（所挑即所见，可预览其他套），其次已绑定套，再回退默认套
  const effectiveBindSetId = computed(() => {
    return (
      selectedBindSetId.value ||
      (scheduleBindings.value[taskConfigKey.value] || {}).configSetId ||
      defaultSetId.value
    )
  })
  function selectBindSet(id) {
    selectedBindSetId.value = id
  }

  // 保存任务配置：编辑的是「本任务配置」草稿；保存写回任务实例（config_json）并解绑配置套。
  // 快照复制模型——任务自持完整配置、与配置套互不影响，多账号共用同一配置套也不会串改。
  // 任务已启用时由调用方先弹覆盖确认。
  async function saveTaskConfig() {
    if (!selectedAccountId.value) return
    const draft = taskConfigDraft.value
    if (!draft) {
      toast('暂无可保存的配置', 'error')
      return
    }
    const errs = validateConfig(draft)
    if (Object.keys(errs).length) {
      formErrors.value = errs
      toast(`保存失败：${Object.values(errs).join('；')}`, 'error')
      return
    }
    const resErrs = validateResources(draft)
    if (Object.keys(resErrs).length) {
      formErrors.value = { ...formErrors.value, ...resErrs }
      toast(`保存失败：${Object.values(resErrs).join('；')}`, 'error')
      return
    }
    formErrors.value = {}
    saving.value = true
    try {
      const scheduleId = await _ensureInstance()
      await api.updateSchedule({ id: scheduleId, config: JSON.parse(JSON.stringify(draft)), configSetId: null })
      await refreshBindings()
      userConfigSets.value = (await api.fetchConfigSets()).userConfigSets
      snapshotSets()
      initTaskDraft()
      toast('已保存到本任务（已与配置套解绑）', 'success')
    } catch (e) {
      toast(e.message || '保存失败', 'error')
    } finally {
      saving.value = false
    }
  }

  // 放弃未保存修改：以来源（任务自身配置 / 绑定套 / 所选套）重新克隆草稿
  async function resetTaskConfig() {
    if (!selectedAccountId.value) return
    saving.value = true
    try {
      userConfigSets.value = (await api.fetchConfigSets()).userConfigSets
      snapshotSets()
      initTaskDraft()
      formErrors.value = {}
    } finally {
      saving.value = false
    }
  }

  async function _ensureInstance() {
    const b = scheduleBindings.value[taskConfigKey.value]
    if (b && b.scheduleId) return b.scheduleId
    const created = await api.createSchedule({ accountId: Number(selectedAccountId.value), taskType: selectedTaskType.value })
    return created.id
  }

  // 启用：实例不存在则创建，把当前草稿配置写入任务实例并开启调度（一步到位）。
  // 保留当前 configSetId 作为「源自」标签（若已解绑则为 null）。
  async function enableTask() {
    if (!selectedAccountId.value) {
      toast('请先选择账号', 'error')
      return false
    }
    const draft = taskConfigDraft.value
    if (!draft) {
      toast('请先完善配置', 'error')
      return false
    }
    const errs = validateConfig(draft)
    if (Object.keys(errs).length) {
      formErrors.value = errs
      toast(`启用失败：${Object.values(errs).join('；')}`, 'error')
      return false
    }
    const resErrs = validateResources(draft)
    if (Object.keys(resErrs).length) {
      formErrors.value = { ...formErrors.value, ...resErrs }
      toast(`启用失败：${Object.values(resErrs).join('；')}`, 'error')
      return false
    }
    formErrors.value = {}
    saving.value = true
    try {
      const scheduleId = await _ensureInstance()
      const b = scheduleBindings.value[taskConfigKey.value]
      await api.updateSchedule({
        id: scheduleId,
        enabled: true,
        config: JSON.parse(JSON.stringify(draft)),
        configSetId: b && b.configSetId ? Number(b.configSetId) : null,
      })
      await refreshBindings()
      initTaskDraft()
      toast('定时任务已启用', 'success')
      return true
    } catch (e) {
      toast(e.message || '启用失败', 'error')
      return false
    } finally {
      saving.value = false
    }
  }

  // 暂停：仅关闭调度，保留实例与绑定（删除实例请到定时任务页）
  async function pauseTask() {
    const b = scheduleBindings.value[taskConfigKey.value]
    if (!b || !b.scheduleId) return false
    saving.value = true
    try {
      await api.updateSchedule({ id: b.scheduleId, enabled: false })
      await refreshBindings()
      toast('已暂停调度', 'success')
      return true
    } catch (e) {
      toast(e.message || '暂停失败', 'error')
      return false
    } finally {
      saving.value = false
    }
  }

  // 换绑：把所选配置套的配置快照复制进本任务实例（覆盖），并保留为源自标签；不影响其他任务。
  async function bindSet(setId) {
    const b = scheduleBindings.value[taskConfigKey.value]
    if (!b || !b.scheduleId) {
      selectBindSet(setId)
      return true
    }
    const set = userConfigSets.value.find((s) => s.id === setId)
    if (!set) return false
    saving.value = true
    try {
      await api.updateSchedule({
        id: b.scheduleId,
        config: JSON.parse(JSON.stringify(set.config)),
        configSetId: setId == null ? null : Number(setId),
      })
      await refreshBindings()
      initTaskDraft()
      toast('已换绑并复制配置套到本任务', 'success')
      return true
    } catch (e) {
      toast(e.message || '换绑失败', 'error')
      return false
    } finally {
      saving.value = false
    }
  }

  // 手动套用：创建实例（如无）并把当前所选配置套的配置快照复制进本任务；不改变启用状态。
  async function applyBind() {
    const setId = effectiveBindSetId.value
    if (!setId || !selectedAccountId.value) {
      toast('请先选择账号与配置套', 'error')
      return false
    }
    const set = userConfigSets.value.find((s) => s.id === setId)
    if (!set) return false
    saving.value = true
    try {
      const scheduleId = await _ensureInstance()
      await api.updateSchedule({
        id: scheduleId,
        config: JSON.parse(JSON.stringify(set.config)),
        configSetId: Number(setId),
      })
      await refreshBindings()
      initTaskDraft()
      toast('已套用配置套到本任务', 'success')
      return true
    } catch (e) {
      toast(e.message || '套用失败', 'error')
      return false
    } finally {
      saving.value = false
    }
  }

  // 应用全部：把当前配置套配置覆盖写入所有「已套用」该套的账号任务配置（后端批量执行）。
  // 覆盖后重拉绑定与配置套，使任务状态即时反映「已套用」对齐态。
  async function applyConfigSetToAll(setId) {
    if (!setId) return
    saving.value = true
    try {
      const data = await api.applyConfigSetToAll(setId)
      const n = (data && data.updated) || 0
      await refreshBindings()
      userConfigSets.value = (await api.fetchConfigSets()).userConfigSets
      snapshotSets()
      initTaskDraft()
      if (n) toast(`已应用配置套到 ${n} 个关联账号任务`, 'success')
      else toast('没有套用该配置套的账号任务配置', 'warning')
    } catch (e) {
      toast(e.message || '应用失败', 'error')
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
  async function trashImage(id, opts) {
    saving.value = true
    try {
      imageLibrary.value = await api.trashImage(id, opts)
    } finally {
      saving.value = false
    }
  }
  async function restoreImage(id, opts) {
    saving.value = true
    try {
      imageLibrary.value = await api.restoreImage(id, opts)
    } finally {
      saving.value = false
    }
  }
  async function deleteImage(id, opts) {
    saving.value = true
    try {
      imageLibrary.value = await api.deleteImage(id, opts)
      // 记录已物理删除，同步释放缩略图 objectURL（缓存只增不减会跨会话残留）
      api.releaseImageBlob(id)
    } finally {
      saving.value = false
    }
  }
  // 手动标记为已使用（图库页演示/手动流转；recycle 策略消费后也落到 used 状态）
  async function markUsed(id, opts) {
    saving.value = true
    try {
      imageLibrary.value = await api.markImageUsed(id, opts)
    } finally {
      saving.value = false
    }
  }
  // 上传图片：走真实归一化管线，成功后刷新图库数组（groupId 指定上传目标分组）
  // onProgress 透传单张上传进度（0~100），供图库页批量/拖拽上传展示进度；
  // opts.silent 透传批量上传（队列 UI 自行展示逐文件失败），单张上传不传走全局 toast
  async function uploadImage(file, groupId = null, onProgress, opts) {
    saving.value = true
    try {
      imageLibrary.value = await api.uploadImage(file, groupId, onProgress, opts)
    } finally {
      saving.value = false
    }
  }

  // ── 图库分组（相册）：同寝室账号共用一组，不同寝室各建各的组 ──
  async function createImageGroup(name) {
    saving.value = true
    try {
      imageGroups.value = await api.createImageGroup(name)
      return imageGroups.value
    } finally {
      saving.value = false
    }
  }
  async function renameImageGroup(id, name) {
    saving.value = true
    try {
      imageGroups.value = await api.renameImageGroup(id, name)
    } finally {
      saving.value = false
    }
  }
  async function deleteImageGroup(id) {
    saving.value = true
    try {
      const { imageGroups: groups, imageLibrary: lib } = await api.deleteImageGroup(id)
      imageGroups.value = groups
      imageLibrary.value = lib
    } finally {
      saving.value = false
    }
  }
  async function moveImage(id, groupId = null, opts) {
    saving.value = true
    try {
      imageLibrary.value = await api.moveImageToGroup(id, groupId, opts)
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
  // 测试推送：真实发送一条样例消息到该凭证通道，验证可用性
  async function testPushCredential(id, template = 'html') {
    await api.testPushCredential(id, template)
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
    // 切换任务时清掉未绑定任务的本地选套预览，回落到默认套，避免跨任务串味
    selectedBindSetId.value = ''
  }

  // 切换账号/任务时重新初始化编辑草稿（以任务自身配置或绑定套为来源）
  watch([selectedAccountId, selectedTaskType], () => initTaskDraft())

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
    refreshing,
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
    imageGroups,
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
    taskAlignedWithSource,
    taskConfigMetaOf,
    isDirty,
    activeSetDirty,
    taskScheduleState,
    accountTree,
    locationOptions,
    credentialOptions,
    credentialOptionsByChannel,
    uaOptions,
    channelOptions,
    setOptions,
    load,
    refreshBindings,
    saveActiveSet,
    createConfigSet,
    deleteConfigSet,
    renameConfigSet,
    selectedBindSetId,
    effectiveBindSetId,
    selectBindSet,
    enableTask,
    pauseTask,
    bindSet,
    applyBind,
    applyConfigSetToAll,
    saveTaskConfig,
    resetActiveSetConfig,
    resetTaskConfig,
    saveLocation,
    deleteLocation,
    trashImage,
    restoreImage,
    deleteImage,
    markUsed,
    uploadImage,
    createImageGroup,
    renameImageGroup,
    deleteImageGroup,
    moveImage,
    saveCredential,
    deleteCredential,
    testPushCredential,
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
