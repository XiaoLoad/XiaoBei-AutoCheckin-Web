// 签到记录接口（mock 阶段：仅前端展示，模拟从 B 平台拉取的第三方签到数据）
// 后续接入真实后端时，仅需替换本文件实现，业务组件无需改动。
// 数据形状见 @/api/types 中的 SignRecord（前后端契约），与后端 schemas 保持一致。
//
// 预留后端接口约定：
//   GET /api/accounts/:id/sign-records   获取指定 B 平台账号的签到记录（第三方数据）
//      query: type=dorm|activity  可选的类型筛选
//   注意：仅按单个账号查询，不聚合全部账号数据（与运营诉求一致）。
import { fetchAccounts } from '@/api/accounts'

const delay = (ms = 400) => new Promise((r) => setTimeout(r, ms))
const pad = (n) => String(n).padStart(2, '0')

// 确定性伪随机：同一账号每次生成的数据稳定，避免刷新后列表跳动
function seeded(seed) {
  let t = (seed | 0) + 0x6d2b79f5
  return function () {
    t += 0x6d2b79f5
    let x = Math.imul(t ^ (t >>> 15), 1 | t)
    x ^= x + Math.imul(x ^ (x >>> 7), 61 | x)
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296
  }
}

const DORM_TASKS = ['寝室晨签', '晚寝签到', '归寝签到']
const ACTIVITY_TASKS = ['主题班会签到', '校园活动签到', '讲座签到']

function makeRecord(id, accountId, accountName, type, date, rand, signed) {
  const time =
    type === 'dorm'
      ? `${pad(7 + Math.floor(rand() * 2))}:${pad(Math.floor(rand() * 60))}`
      : `${pad(18 + Math.floor(rand() * 3))}:${pad(Math.floor(rand() * 60))}`
  const pool = type === 'dorm' ? DORM_TASKS : ACTIVITY_TASKS
  return {
    id,
    accountId,
    taskName: pool[Math.floor(rand() * pool.length)],
    type,
    date,
    time,
    // 已签到：发起人为账号本人；漏签（未签到）：无发起人
    initiator: signed ? accountName || '本人' : '—',
    status: signed ? 'signed' : 'unsigned'
  }
}

// 为单个账号生成近期签到记录（过去 80 天，含今天）
function generate(accountId, accountName) {
  const rand = seeded(accountId * 1000 + 7)
  const today = new Date()
  const records = []
  let id = 1
  for (let back = 80; back >= 0; back--) {
    const d = new Date(today)
    d.setDate(today.getDate() - back)
    const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
    // 寝室签到：每天一条
    records.push(makeRecord(id++, accountId, accountName, 'dorm', date, rand, rand() > 0.14))
    // 活动签到：约 45% 的日期有一条
    if (rand() < 0.45) {
      records.push(makeRecord(id++, accountId, accountName, 'activity', date, rand, rand() > 0.28))
    }
  }
  return records
}

// 获取指定账号的签到记录（第三方数据）。仅取单个账号，不做全量聚合。
export async function fetchSignRecords(accountId, { accountName } = {}) {
  await delay()
  if (!accountId) return []
  return generate(accountId, accountName)
}

// 暴露给 store 用于默认选中第一个账号（复用账号列表接口）
export { fetchAccounts }
