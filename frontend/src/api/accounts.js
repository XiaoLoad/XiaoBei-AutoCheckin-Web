// B 平台账号管理接口（mock 阶段：仅前端展示，使用本地数据模拟异步请求）
// 后续接入真实后端时，仅需替换本文件实现，业务组件无需改动。
//
// 预留后端接口约定：
//   GET    /api/accounts          获取当前用户的 B 平台账号列表
//   POST   /api/accounts          新增账号（含第三方账号密码校验）
//   PUT    /api/accounts/:id       更新账号
//   DELETE /api/accounts/:id       删除账号
//   POST   /api/accounts/verify    校验 B 平台账号密码（调用第三方 API）

let seq = 5
const delay = (ms = 400) => new Promise((r) => setTimeout(r, ms))

function now() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

// 本地 mock 数据：profile 字段为预留个人信息区（登录后由系统自动获取）
const store = [
  {
    id: 1,
    account: 'A-301',
    platform: 'B 打卡平台',
    type: 'dorm',
    enabled: true,
    profile: {
      name: '张三',
      college: '信息科学与工程学院',
      major: '软件工程',
      className: '软工2301',
      studentNo: '2023010101'
    },
    lastSignIn: { time: '2026-08-13 07:58', ok: true },
    createdAt: '2026-03-01 08:30'
  },
  {
    id: 2,
    account: 'A-302',
    platform: 'B 打卡平台',
    type: 'dorm',
    enabled: true,
    profile: {
      name: '李四',
      college: '信息科学与工程学院',
      major: '软件工程',
      className: '软工2301',
      studentNo: '2023010102'
    },
    lastSignIn: { time: '2026-08-13 12:05', ok: true },
    createdAt: '2026-03-02 12:10'
  },
  {
    id: 3,
    account: 'A-305',
    platform: 'B 打卡平台',
    type: 'activity',
    enabled: false,
    profile: {
      name: '王五',
      college: '信息科学与工程学院',
      major: '计算机科学',
      className: '计科2302',
      studentNo: '2023010205'
    },
    lastSignIn: { time: '2026-08-12 22:41', status: 'fail' },
    createdAt: '2026-03-05 09:45'
  },
  {
    id: 4,
    account: 'A-308',
    platform: 'B 打卡平台',
    type: 'general',
    enabled: true,
    profile: { name: '', college: '', major: '', className: '', studentNo: '' },
    lastSignIn: { time: '', status: 'never' },
    createdAt: '2026-04-11 19:20'
  },
  {
    id: 5,
    account: 'A-310',
    platform: 'B 打卡平台',
    type: 'activity',
    enabled: false,
    profile: {
      name: '赵六',
      college: '信息科学与工程学院',
      major: '人工智能',
      className: '智科2301',
      studentNo: '2023010306'
    },
    lastSignIn: { time: '2026-08-09 19:02', status: 'skip' },
    createdAt: '2026-04-15 10:08'
  }
]

function clone(a) {
  return { ...a, profile: { ...a.profile } }
}

// 预留后端查询参数（mock 阶段本地忽略，由组件侧完成筛选演示）：
//   params.keyword    模糊搜索（账号 / 姓名 / 学号）
//   params.type       签到类型过滤：dorm | activity | general
//   params.signStatus 上一次签到状态：success | fail | skip | never
//   params.enabled    启用状态：true | false
export async function fetchAccounts(params = {}) {
  await delay()
  return store.map(clone)
}

export async function createAccount(payload) {
  await delay()
  const item = {
    id: seq++,
    platform: 'B 打卡平台',
    enabled: true,
    lastSignIn: { time: '', status: 'never' },
    createdAt: now(),
    ...payload
  }
  store.push(item)
  return clone(item)
}

export async function updateAccount(id, payload) {
  await delay()
  const i = store.findIndex((a) => a.id === id)
  if (i === -1) throw new Error('账号不存在')
  store[i] = {
    ...store[i],
    ...payload,
    profile: { ...store[i].profile, ...(payload.profile || {}) }
  }
  return clone(store[i])
}

export async function deleteAccount(id) {
  await delay()
  const i = store.findIndex((a) => a.id === id)
  if (i !== -1) store.splice(i, 1)
  return true
}

// 第三方 API 校验账号密码（mock 阶段）
// 规则：账号含 "fail" 或密码为 "wrong" 时判定失败，其余视为校验通过。
export async function verifyAccount(account, password) {
  await delay(600)
  if (!account || !password) {
    return { ok: false, message: '账号和密码不能为空' }
  }
  if (/fail/i.test(account) || password === 'wrong') {
    return { ok: false, message: '账号或密码错误，未能通过 B 平台校验' }
  }
  return { ok: true, message: '账号校验通过，可正常对接 B 平台' }
}

// 演示用扩展数据：补足到约 28 条，使默认每页 10 条时呈现多页，便于前端演示分页逻辑。
// 真实接入后端后，由服务端 total 控制，此处数据可移除。
;(function seedDemoAccounts() {
  const types = ['dorm', 'activity', 'general']
  const statuses = ['success', 'fail', 'skip', 'never']
  const colleges = ['信息科学与工程学院', '机械工程学院', '外国语学院']
  const pad = (n) => String(n).padStart(2, '0')
  for (let i = 6; i <= 28; i++) {
    const t = types[i % 3]
    const st = statuses[i % 4]
    const day = pad((i % 13) + 1)
    const hour = pad((i % 12) + 8)
    store.push({
      id: i,
      account: 'A-' + String(300 + i),
      platform: 'B 打卡平台',
      type: t,
      enabled: i % 4 !== 0,
      profile: {
        name: '同学' + i,
        college: colleges[i % 3],
        major: '专业' + ((i % 5) + 1),
        className: '班级' + i,
        studentNo: '2023' + String(1000 + i)
      },
      lastSignIn:
        st === 'never'
          ? { time: '', status: 'never' }
          : { time: `2026-08-${day} ${hour}:15`, status: st },
      createdAt: '2026-0' + ((i % 9) + 1) + '-10 09:00'
    })
  }
  // 演示数据已占用 id 1~28，新增账号从 29 起，避免与演示数据冲突
  seq = store.length + 1
})()

// 模拟从 B 平台获取账号对应的个人信息（平台回填，用户不可手改）
// 真实接入时改为 GET /api/accounts/:id/profile 或登录后由后端注入。
export async function fetchProfile(account) {
  await delay(600)
  const seed = (account || 'x').split('').reduce((s, c) => s + c.charCodeAt(0), 0)
  return {
    name: '平台用户' + (seed % 90 + 10),
    college: '信息科学与工程学院',
    major: '软件工程',
    className: '软工' + (seed % 2300 + 2301),
    studentNo: '2023' + String(seed % 9000 + 1000)
  }
}
