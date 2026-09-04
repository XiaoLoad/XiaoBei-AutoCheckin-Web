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
    // 平台回填档案：姓名作主视觉，学院/专业作次行；mapItem 须显式透传，否则会被归一化丢弃
    studentName: it.studentName || '',
    college: it.college || '',
    major: it.major || '',
    mode: it.mode || 'follow',
    configSetId: it.configSetId == null ? null : it.configSetId,
    config: it.config || null,
    custom: normalizeCustom(it.custom),
    overrides: it.overrides || {},
    enabled: !!it.enabled,
    // nextRunAt 为未叠加随机延迟的基线时刻（后端唯一事实源）；nextRunJitterMin 供卡片标注「±N分」
    nextRunAt: it.nextRunAt || '',
    nextRunJitterMin: it.nextRunJitterMin || 0,
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

// 更新单个定时任务（保存定时设置：mode / custom / config / 绑定变更）
// silent：调用方（schedules / signConfig store）均自带 catch+toast，关闭全局提示避免双重
export async function updateSchedule(payload) {
  const { id, ...rest } = payload
  const data = await request({ url: `/schedules/${id}`, method: 'put', data: rest, silent: true })
  return mapItem(data)
}

// 开启 / 暂停 单个定时任务
export async function toggleSchedule(id, enabled) {
  const data = await request({ url: `/schedules/${id}`, method: 'put', data: { enabled }, silent: true })
  return mapItem(data)
}

// 显式创建定时任务实例（账号 × 任务类型）
export async function createSchedule(payload) {
  const data = await request({
    url: '/schedules', method: 'post',
    data: { accountId: payload.accountId, taskType: payload.taskType },
    silent: true
  })
  return mapItem(data)
}

// 删除定时任务实例
export async function deleteSchedule(id) {
  await request({ url: `/schedules/${id}`, method: 'delete', silent: true })
}

// ── 任务实例与配置套的绑定（真实 /api/schedules）──
// 返回 { `${accountId}:${taskType}`: { scheduleId, configSetId, enabled, overrides, 运行信息 } }，
// configSetId 为 null 表示未绑定；overrides 为字段级覆盖（顶层配置键 → 替换值）。
// [类型约定] id 统一字符串化：需与 userConfigSets 的 id（mapSetIn 已 String）严格相等匹配
// silent：signConfig.refreshBindings 刻意吞错降级为空绑定，失败不打扰全局
export async function fetchScheduleBindings() {
  const data = await request({ url: '/schedules', method: 'get', silent: true })
  const map = {}
  for (const s of (data.items || [])) {
    map[`${s.accountId}:${s.taskType}`] = {
      scheduleId: String(s.id),
      configSetId: s.configSetId == null ? null : String(s.configSetId),
      config: s.config || null,
      enabled: !!s.enabled,
      overrides: s.overrides || {},
      nextRunAt: s.nextRunAt || '',
      lastRunAt: s.lastRunAt || '',
      lastStatus: s.lastStatus || 'never'
    }
  }
  return map
}

// 批量管理：对一批「账号 × 任务类型」统一开启或关闭调度（action='enable'|'disable'）。
// body: { action, targets:[{accountId,taskType}], configSetId? }
// 后端返回 {action, affected, skipped, skippedReasons, affectedList}
export async function batchManageSchedules(payload) {
  const data = await request({ url: '/schedules/batch-manage', method: 'post', data: payload, silent: true })
  return data || {}
}

// 将某配置套应用到任务：仅传 configSetId，后端自动置 mode=follow
// （历史上另有 bindScheduleConfigSet 直通包装，已随「套用即快照」语义并入 updateSchedule 删除）
