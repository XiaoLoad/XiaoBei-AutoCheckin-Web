// 定时任务模块 API（已接真实 /api/schedules）。
// 调度任务 = 平台账号 × 任务类型 的笛卡尔积：每个「账号 + 签到类型」实例对应一个定时任务，
// 用于开启/管理该实例的自动签到调度。列表与开关走真实接口；任务与配置套的绑定见下方两个函数。
import request from '@/api/request'

// 后端 item → 前端卡片契约：补齐缺省 custom，统一 lastRun / nextRunAt 字段名
function normalizeCustom(c) {
  c = c || {}
  return {
    hour: typeof c.hour === 'number' ? c.hour : 8,
    minute: typeof c.minute === 'number' ? c.minute : 0,
    weekdays: Array.isArray(c.weekdays) ? c.weekdays : [1, 2, 3, 4, 5, 6, 7],
    randomDelayMax: typeof c.randomDelayMax === 'number' ? c.randomDelayMax : 5
  }
}

function mapItem(it) {
  return {
    id: it.id,
    accountId: it.accountId,
    accountName: it.accountName || '',
    accountEnabled: !!it.accountEnabled,
    taskType: it.taskType,
    taskLabel: it.taskLabel || (it.taskType === 'dorm' ? '寝室签到' : '活动签到'),
    platform: it.platform || '',
    studentNo: it.studentNo || '',
    className: it.className || '',
    mode: it.mode || 'follow',
    configSetId: it.configSetId == null ? null : it.configSetId,
    custom: normalizeCustom(it.custom),
    enabled: !!it.enabled,
    nextRunAt: it.nextRunAt || '',
    lastRun: it.lastRunAt || '',
    lastStatus: it.lastStatus || 'never',
    runCount: it.runCount || 0
  }
}

// 列出全部定时任务（账号 × 任务类型）
export async function fetchSchedules() {
  const data = await request({ url: '/schedules', method: 'get' })
  return (data.items || []).map(mapItem)
}

// 更新单个定时任务（保存定时设置：mode / custom）
export async function updateSchedule(payload) {
  const { id, ...rest } = payload
  const data = await request({ url: `/schedules/${id}`, method: 'put', data: rest })
  return mapItem(data)
}

// 开启 / 暂停 单个定时任务
export async function toggleSchedule(id, enabled) {
  const data = await request({ url: `/schedules/${id}`, method: 'put', data: { enabled } })
  return mapItem(data)
}

// ── 任务实例与配置套的绑定（真实 /api/schedules）──
// 返回 { `${accountId}:${taskType}`: { scheduleId, configSetId } }，configSetId 为 null 表示未绑定
export async function fetchScheduleBindings() {
  const data = await request({ url: '/schedules', method: 'get' })
  const map = {}
  for (const s of (data.items || [])) {
    map[`${s.accountId}:${s.taskType}`] = {
      scheduleId: String(s.id),
      configSetId: s.configSetId == null ? null : String(s.configSetId)
    }
  }
  return map
}

// 将某配置套应用到任务：仅传 configSetId，后端自动置 mode=follow
export async function bindScheduleConfigSet(scheduleId, configSetId) {
  const data = await request({
    url: `/schedules/${scheduleId}`,
    method: 'put',
    data: { configSetId: configSetId == null ? null : Number(configSetId) }
  })
  return mapItem(data)
}
