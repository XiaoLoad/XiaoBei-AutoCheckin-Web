// 签到类型徽标的唯一出处，两条互不相通的轴：
//   账号轴——一个账号能签什么，按「已添加至定时任务且启用」的 signTasks 派生；
//   任务轴——某一条任务是哪一类，入参是 B 平台任务类型码 dorm|activity。
//
// b_accounts.type 是创建时的死值（新增/编辑弹窗没有这个字段，界面建的账号一律落到 schema
// 缺省 'general'），读它只会让所有账号显示同一个标签；判定只能看任务启用态。
// 账号轴口径与后端 /me 的 _type_code 一致：两类都启用→general，仅其一→该类型，都没启用→none。
export const ACCOUNT_TYPE_META = {
  general: { label: '寝室 + 活动', cls: 'bg-ink/10 text-ink-soft' },
  dorm: { label: '寝室签到', cls: 'bg-brand/10 text-brand' },
  activity: { label: '活动签到', cls: 'bg-info/10 text-info' },
  none: { label: '未配置任务', cls: 'bg-ink/5 text-ink-muted' },
}

export function accountTypeCode(signTasks) {
  const st = signTasks || []
  const on = (t) => st.some((x) => x.type === t && x.enabled)
  const dorm = on('dorm')
  const activity = on('activity')
  if (dorm && activity) return 'general'
  if (dorm) return 'dorm'
  if (activity) return 'activity'
  return 'none'
}

export function accountTypeMetaByCode(code) {
  return ACCOUNT_TYPE_META[code] || ACCOUNT_TYPE_META.none
}

export function accountTypeMeta(signTasks) {
  return accountTypeMetaByCode(accountTypeCode(signTasks))
}

// 同一轴的三处形态收在一张表里：cls 供徽标、solid 供实心色块（左侧色条、进度条）、
// short 供紧凑处（分桶按钮、配置套下拉项）。
// 「未知」分支不可达（B 平台只回 dorm/activity），但保留以免将来新增类别时静默显示错标签。
export const TASK_TYPE_META = {
  dorm: { label: '寝室签到', short: '寝室', cls: 'bg-brand/10 text-brand', solid: 'bg-brand' },
  activity: { label: '活动签到', short: '活动', cls: 'bg-info/10 text-info', solid: 'bg-info' },
  unknown: { label: '未知类型', short: '未知', cls: 'bg-ink/5 text-ink-soft', solid: 'bg-ink/20' },
}

export function taskTypeMeta(code) {
  return TASK_TYPE_META[code] || TASK_TYPE_META.unknown
}
