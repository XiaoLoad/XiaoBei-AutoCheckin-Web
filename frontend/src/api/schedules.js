// 定时任务模块 API（前端框架阶段：返回 mock 数据，模拟网络延迟）。
// 调度任务 = 平台账号 × 任务类型 的笛卡尔积：每个「账号 + 签到类型」实例对应一个定时任务，
// 用于开启/管理该实例的自动签到调度。后端就绪后，把函数体替换为对 request 的调用即可。
import * as signConfigApi from '@/api/signConfig'

const delay = (ms = 200) => new Promise((r) => setTimeout(r, ms))
const clone = (v) => JSON.parse(JSON.stringify(v))

// mock 数据源：延迟构建（首次访问时根据账号/任务类型生成）
const mock = { schedules: [] }

async function ensureSchedules() {
  if (mock.schedules.length) return
  const meta = await signConfigApi.fetchConfigMeta()
  const accounts = meta.accounts
  const taskTypes = meta.taskTypes
  let i = 0
  for (const a of accounts) {
    for (const t of taskTypes) {
      const accountEnabled = a.status === 'enabled'
      mock.schedules.push({
        id: `sch_${a.id}_${t.value}`,
        accountId: a.id,
        accountName: a.name,
        studentNo: a.studentNo,
        className: a.className,
        platform: a.platform,
        taskType: t.value,
        taskLabel: t.label,
        accountEnabled, // 底层账号是否启用：未启用则定时任务不可开启
        enabled: accountEnabled, // 默认跟随账号启用态
        mode: 'follow', // follow 跟随配置套 / custom 自定义执行时刻
        custom: { hour: 8, minute: 0, weekdays: [1, 2, 3, 4, 5, 6, 7], randomDelayMax: 5 },
        lastRun: accountEnabled ? new Date(Date.now() - ((i % 4) + 1) * 3 * 3600 * 1000).toISOString() : null,
        lastStatus: accountEnabled ? (i % 5 === 0 ? 'fail' : i % 3 === 0 ? 'skip' : 'success') : null,
        runCount: accountEnabled ? 20 + i * 3 : 0
      })
      i++
    }
  }
}

// 列出全部定时任务（账号 × 任务类型）
export async function fetchSchedules() {
  await delay()
  await ensureSchedules()
  return clone(mock.schedules || mock.schedules)
}

// 更新单个定时任务（保存定时设置：mode / custom）
export async function updateSchedule(payload) {
  await delay()
  await ensureSchedules()
  const i = mock.schedules.findIndex((s) => s.id === payload.id)
  if (i !== -1) mock.schedules[i] = { ...mock.schedules[i], ...payload }
  return clone(mock.schedules[i])
}

// 开启 / 暂停 单个定时任务
export async function toggleSchedule(id, enabled) {
  await delay()
  await ensureSchedules()
  const s = mock.schedules.find((x) => x.id === id)
  if (s) s.enabled = enabled
  return clone(s)
}

// ── 模块 C：任务实例与配置套的绑定（真实 /api/schedules）──
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
  return data
}
