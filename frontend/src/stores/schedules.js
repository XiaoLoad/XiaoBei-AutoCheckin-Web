// 定时任务领域状态（Pinia）：收纳账号 × 任务类型的调度任务、开启/暂停、定时设置。
// 后端接入时只需改 api/schedules.js，本 store 与视图无需变动。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { toast } from '@/utils/toast'
import * as api from '@/api/schedules'
import * as signConfigApi from '@/api/signConfig'
import { computeNextRun, formatNextRun, nextRunSummary } from '@/utils/schedule'

export const useSchedulesStore = defineStore('schedules', () => {
  const loading = ref(true)
  const saving = ref(false)
  const schedules = ref([])

  // 读取某任务实例的配置套元信息（用于"跟随配置套"预览与下次执行计算）
  function configMetaOf(accountId, taskType) {
    return signConfigApi.getTaskConfigMeta(accountId, taskType)
  }
  // 计算某任务的"下一次执行" Date
  function nextRunOf(s) {
    return computeNextRun(s.mode, s.custom, configMetaOf(s.accountId, s.taskType))
  }
  // 计算某任务的"下一次执行"可读文案
  function nextRunTextOf(s) {
    return formatNextRun(nextRunOf(s)).text
  }
  // 模式摘要文案（卡片 chip 使用）
  function nextRunSummaryOf(s) {
    return nextRunSummary(s.mode, s.custom, configMetaOf(s.accountId, s.taskType))
  }

  async function load() {
    loading.value = true
    try {
      schedules.value = await api.fetchSchedules()
    } finally {
      loading.value = false
    }
  }

  // 开启 / 暂停：底层账号未启用的任务不可开启
  async function toggle(id, enabled) {
    const cur = schedules.value.find((s) => s.id === id)
    if (!cur) return
    if (enabled && !cur.accountEnabled) {
      toast('该平台账号未启用，无法开启定时', 'error')
      return
    }
    saving.value = true
    try {
      const updated = await api.toggleSchedule(id, enabled)
      const i = schedules.value.findIndex((s) => s.id === id)
      if (i !== -1) schedules.value[i] = updated
    } finally {
      saving.value = false
    }
  }

  // 保存定时设置（mode / custom）
  async function saveSettings(id, patch) {
    if (patch.mode === 'custom' && (!patch.custom.weekdays || patch.custom.weekdays.length === 0)) {
      toast('请至少选择一个执行星期', 'error')
      return
    }
    saving.value = true
    try {
      const updated = await api.updateSchedule({ id, ...patch })
      const i = schedules.value.findIndex((s) => s.id === id)
      if (i !== -1) schedules.value[i] = updated
      toast('定时设置已保存', 'success')
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

  return {
    loading,
    saving,
    schedules,
    configMetaOf,
    nextRunOf,
    nextRunTextOf,
    nextRunSummaryOf,
    load,
    toggle,
    saveSettings,
    stats
  }
})
