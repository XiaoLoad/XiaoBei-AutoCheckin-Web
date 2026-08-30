// 定时任务领域状态（Pinia）：收纳账号 × 任务类型的调度任务、开启/暂停、定时设置。
// 已接真实 /api/schedules：本 store 负责开启前预校验与错误兜底，视图无需关心接口细节。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { toast } from '@/utils/toast'
import * as api from '@/api/schedules'
import { useSignConfigStore } from '@/stores/signConfig'
import { nextRunSummary } from '@/utils/schedule'

// 开启前预校验：返回 null 表示可开启，否则返回错误文案（与后端 4401/4402 呼应）
function enableBlockReason(s) {
  if (!s.accountEnabled) return '该平台账号未启用，无法开启定时（请先在「账号管理」启用该账号）'
  if (s.mode === 'follow' && !s.configSetId) return '请先在「签到配置」为该任务绑定配置套后再开启'
  if (s.mode === 'standalone' && !s.config) return '请先在「签到配置」完善本任务配置后再开启'
  if (s.mode === 'custom') {
    const c = s.custom || {}
    if (!Array.isArray(c.weekdays) || c.weekdays.length === 0) return '请先在「定时设置」中选择执行星期'
    if (typeof c.hour !== 'number' || typeof c.minute !== 'number') return '请先在「定时设置」中设置执行时刻'
  }
  return null
}

export const useSchedulesStore = defineStore('schedules', () => {
  const loading = ref(false)
  // 无感刷新：已有数据时后台静默换新（视图仅降透明），loading 只用于真正的首次加载
  const refreshing = ref(false)
  const loaded = ref(false)
  let loadSeq = 0
  const saving = ref(false)
  const schedules = ref([])

  // 读取某任务实例的配置元信息：standalone 任务优先读自身 config；否则回退配置套元信息
  function configMetaOf(accountId, taskType) {
    const s = schedules.value.find((x) => x.accountId == accountId && x.taskType === taskType)
    if (s && s.config) {
      const cfg = s.config
      const sign = useSignConfigStore()
      const loc =
        sign.userLocations.find((l) => l.id === cfg.locationId) ||
        sign.systemLocations.find((l) => l.id === cfg.locationId)
      return {
        time: cfg.time ? JSON.parse(JSON.stringify(cfg.time)) : null,
        presetSetName: s.configSetId ? '原配置套' : '自定义',
        locationName: loc ? loc.name : '未设置位置'
      }
    }
    return useSignConfigStore().taskConfigMetaOf(accountId, taskType)
  }
  // 模式摘要文案（卡片 chip 使用）。下次执行时间的唯一事实源是后端 nextRunAt
  // （含 jitter 口径，见 utils/schedule.js 头注释）；本地不再重复实现一份计算
  function nextRunSummaryOf(s) {
    return nextRunSummary(s.mode, s.custom, configMetaOf(s.accountId, s.taskType))
  }

  async function load() {
    const first = !loaded.value
    if (first) loading.value = true
    else refreshing.value = true
    const seq = ++loadSeq
    try {
      const list = await api.fetchSchedules()
      if (seq !== loadSeq) return // 竞态守卫：仅采纳最新请求
      schedules.value = list
      loaded.value = true
    } finally {
      if (seq === loadSeq) {
        loading.value = false
        refreshing.value = false
      }
    }
  }

  // 开启 / 暂停：底层账号未启用、或未绑定配置套的任务不可开启
  async function toggle(id, enabled) {
    const cur = schedules.value.find((s) => s.id === id)
    if (!cur) return
    if (enabled) {
      const reason = enableBlockReason(cur)
      if (reason) {
        toast(reason, 'error')
        return
      }
    }
    saving.value = true
    try {
      const updated = await api.toggleSchedule(id, enabled)
      const i = schedules.value.findIndex((s) => s.id === id)
      if (i !== -1) schedules.value[i] = updated
    } catch (e) {
      toast(e.message || '操作失败', 'error')
    } finally {
      saving.value = false
    }
  }

  // 保存定时设置（mode / custom）
  async function saveSettings(id, patch) {
    const cur = schedules.value.find((s) => s.id === id)
    if (!cur) return
    if (patch.mode === 'follow' && !cur.configSetId) {
      toast('请先在「签到配置」为该任务绑定配置套后再保存', 'error')
      return
    }
    if (patch.mode === 'custom') {
      const c = patch.custom || {}
      if (!Array.isArray(c.weekdays) || c.weekdays.length === 0) {
        toast('请至少选择一个执行星期', 'error')
        return
      }
      if (typeof c.hour !== 'number' || typeof c.minute !== 'number') {
        toast('请设置合法的小时与分钟', 'error')
        return
      }
    }
    saving.value = true
    try {
      const updated = await api.updateSchedule({ id, ...patch })
      const i = schedules.value.findIndex((s) => s.id === id)
      if (i !== -1) schedules.value[i] = updated
      toast('定时设置已保存', 'success')
    } catch (e) {
      toast(e.message || '保存失败', 'error')
    } finally {
      saving.value = false
    }
  }

  // 概览统计
  const stats = computed(() => {
    const list = schedules.value
    const total = list.length
    const enabled = list.filter((s) => s.enabled && s.accountEnabled).length
    const accountOff = list.filter((s) => !s.accountEnabled).length
    const stopped = list.filter((s) => s.accountEnabled && !s.enabled).length
    // 按任务类型统计（运行中 = 账号已启用且已开启）
    const dormEnabled = list.filter((s) => s.taskType === 'dorm' && s.enabled && s.accountEnabled).length
    const activityEnabled = list.filter((s) => s.taskType === 'activity' && s.enabled && s.accountEnabled).length
    const dormTotal = list.filter((s) => s.taskType === 'dorm').length
    const activityTotal = list.filter((s) => s.taskType === 'activity').length
    return { total, enabled, accountOff, stopped, dormEnabled, activityEnabled, dormTotal, activityTotal }
  })

  // 显式创建任务实例（账号 × 任务类型）
  async function addTask(payload) {
    saving.value = true
    try {
      const created = await api.createSchedule(payload)
      const i = schedules.value.findIndex((s) => s.id === created.id)
      if (i === -1) schedules.value.push(created)
      else schedules.value[i] = created
      toast('定时任务已创建', 'success')
      return created
    } catch (e) {
      toast(e.message || '创建失败', 'error')
      return null
    } finally {
      saving.value = false
    }
  }

  // 删除任务实例
  async function removeTask(id) {
    saving.value = true
    try {
      await api.deleteSchedule(id)
      schedules.value = schedules.value.filter((s) => s.id !== id)
      toast('定时任务已删除', 'success')
    } catch (e) {
      toast(e.message || '删除失败', 'error')
    } finally {
      saving.value = false
    }
  }

  return {
    loading,
    refreshing,
    saving,
    schedules,
    configMetaOf,
    nextRunSummaryOf,
    load,
    toggle,
    saveSettings,
    addTask,
    removeTask,
    stats
  }
})
