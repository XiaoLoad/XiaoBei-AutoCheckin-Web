// 用户日志（操作审计）的文案唯一出处：分类、结果、动作、会话收口原因、变更字段的中文说法
// 全部集中在此。视图、筛选条、指标行、会话卡共用一份，避免同一动作在多处各写一套中文后叫法漂移。
// 后端只回码值（category/action/field/closeReason），中文一律在前端查表——
// 与 accountType.js、pushChannels.js 同一条约定。
//
// 配色来自设计稿：认证=品牌蓝、变更=琥珀、配置=灰（配置类事件后端尚未埋点，配色先留好，
// 一旦补上埋点即可直接显示，不必回头改这里）。
export const OP_CATEGORY_META = {
  auth: { label: '认证', icon: 'shield', dot: 'bg-brand', cls: 'bg-brand/10 text-brand' },
  user: { label: '变更', icon: 'users', dot: 'bg-warning', cls: 'bg-warning/10 text-warning' },
  pool: { label: '配置', icon: 'sliders', dot: 'bg-ink/40', cls: 'bg-ink/5 text-ink-muted' },
}

export const OP_RESULT_META = {
  success: { label: '成功', cls: 'bg-success/10 text-success', solid: 'bg-success' },
  fail: { label: '失败', cls: 'bg-danger/10 text-danger', solid: 'bg-danger' },
}

// 会话收口原因：logout=正常；ongoing=进行中；expired=令牌到期仍无登出记录；
// superseded=同账号再次登录把上一段顶掉；orphan=有操作但查不到对应登录（历史数据或残留令牌）
export const OP_CLOSE_META = {
  logout: { label: '已正常登出', cls: 'bg-success/10 text-success' },
  ongoing: { label: '会话进行中', cls: 'bg-brand/10 text-brand' },
  expired: { label: '超时未登出', cls: 'bg-warning/10 text-warning' },
  superseded: { label: '被新登录顶替', cls: 'bg-ink/5 text-ink-muted' },
  orphan: { label: '无登录记录', cls: 'bg-ink/5 text-ink-muted' },
}

// 动作表：label 用于筛选下拉；category 供跨表推导（后端已回 category，此处仅作兜底）。
// 键必须与后端 backend/app/services/op_log.py 的 ACTION_* 常量一一对应——
// 那是动作码的唯一事实源，这里只是给它配中文。后端新增动作而这里没跟上时，
// opActionMeta 会走下面的兜底把码值（如 pool.create）原样显示给管理员。
export const OP_ACTION_META = {
  'auth.login': { label: '登录', category: 'auth' },
  'auth.logout': { label: '退出登录', category: 'auth' },
  'auth.password': { label: '修改密码', category: 'auth' },
  'user.create': { label: '新建用户', category: 'user' },
  'user.update': { label: '编辑用户', category: 'user' },
  'user.enable': { label: '启用用户', category: 'user' },
  'user.disable': { label: '禁用用户', category: 'user' },
  'user.delete': { label: '删除用户', category: 'user' },
}

// 筛选下拉里动作的排列顺序＝上表的声明顺序（认证组在前、用户变更组在后）。
// 不按字母序：那会把 auth.* 与 user.* 交错排开，读起来没有业务含义，
// 而这张表本来就是按类别分段写的，顺序现成。
const OP_ACTION_ORDER = Object.keys(OP_ACTION_META)

// 未登记的动作排到最后（它们本身也是「该回来补这张表」的信号）。
// 同档内再按码值字典序兜底，保证结果与输入顺序无关。
export function opActionSortKey(code) {
  const i = OP_ACTION_ORDER.indexOf(code)
  return i === -1 ? OP_ACTION_ORDER.length : i
}

// 变更明细的字段名（detail.changes[].field）
export const OP_FIELD_LABELS = {
  username: '用户名',
  role: '角色',
  enabled: '状态',
  quota: '额度',
}

export function opCategoryMeta(code) {
  return OP_CATEGORY_META[code] || { label: code || '其他', icon: 'records', dot: 'bg-ink/30', cls: 'bg-ink/5 text-ink-muted' }
}

export function opResultMeta(code) {
  return OP_RESULT_META[code] || OP_RESULT_META.success
}

export function opCloseMeta(code) {
  return OP_CLOSE_META[code] || OP_CLOSE_META.orphan
}

// 兜底刻意原样吐码值：这是「后端加了动作、这张表没跟上」的唯一可见症状。
// 硬翻成半中半英反而像翻译出错，不如让它显眼。
export function opActionMeta(code) {
  return OP_ACTION_META[code] || { label: code || '未知操作', category: '' }
}

export function opFieldLabel(field) {
  return OP_FIELD_LABELS[field] || field
}

export function opRoleLabel(role) {
  if (role === 'admin') return '管理员'
  if (role === 'user') return '普通用户'
  return '系统'
}

// 变更值的可读化：布尔与角色码直接落库，展示时转中文；null 表示当时无值
export function opFieldValue(field, v) {
  if (v === null || v === undefined || v === '') return '—'
  if (field === 'enabled') return v ? '启用' : '禁用'
  if (field === 'role') return v === 'admin' ? '管理员' : v === 'user' ? '普通用户' : String(v)
  return String(v)
}

// 时间轴上的事件文案：单字段变更渲染成「额度 100 → 150（用户 liuyang）」，
// 比笼统的「修改用户「liuyang」」信息量大得多——前者一眼看出改了什么，后者还要点开详情。
export function opEventText(row) {
  const d = row && row.detail
  const changes = d && Array.isArray(d.changes) ? d.changes : []
  const target = (d && d.targetUsername) || ''
  if (changes.length === 1) {
    const c = changes[0]
    const base = `${opFieldLabel(c.field)} ${opFieldValue(c.field, c.from)} → ${opFieldValue(c.field, c.to)}`
    return target ? `${base}（用户 ${target}）` : base
  }
  if (changes.length > 1) {
    return `${row.summary || '—'}（${changes.map((c) => opFieldLabel(c.field)).join('、')}）`
  }
  return (row && row.summary) || '—'
}

// 会话时长：进行中前缀「已」（设计稿「已 12 分钟」），已结束直接给时长
export function opDurationText(seconds, running) {
  const s = Math.max(0, Number(seconds) || 0)
  let label
  if (s < 60) label = '不到 1 分钟'
  else if (s < 3600) label = `${Math.round(s / 60)} 分钟`
  else if (s < 86400) {
    const h = s / 3600
    label = `${h >= 10 || Number.isInteger(h) ? Math.round(h) : h.toFixed(1)} 小时`
  } else label = `${Math.round(s / 86400)} 天`
  return running ? `已 ${label}` : label
}

// 会话时间跨度：'09-16 08:12 → 08:47'，同一天只在末尾给时刻，跨天才补全日期
export function opSessionSpan(s) {
  const start = (s.startAt || '').slice(5)
  if (!start) return ''
  if (s.running) return `${start} → 现在`
  const end = (s.endAt || '').slice(5)
  if (!end) return start
  const sameDay = end.slice(0, 5) === start.slice(0, 5)
  return `${start} → ${sameDay ? end.slice(5) : end}`
}

// 日期分节带：日志页按日分段，标题需区分「今天 / 昨天」这类相对说法，
// 日期 key 一律用本地年月日拼装（禁用 toISOString，UTC 会差一天）
export function opDateKey(createdAt) {
  const raw = (createdAt || '').slice(0, 10)
  if (raw) return raw
  const d = new Date(createdAt)
  if (Number.isNaN(d.getTime())) return ''
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export function opDayLabel(dayKey) {
  if (!dayKey) return '未知日期'
  const p = (n) => String(n).padStart(2, '0')
  const now = new Date()
  const today = `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`
  const y = new Date(now.getTime() - 86400000)
  const yesterday = `${y.getFullYear()}-${p(y.getMonth() + 1)}-${p(y.getDate())}`
  if (dayKey === today) return `今天 · ${dayKey}`
  if (dayKey === yesterday) return `昨天 · ${dayKey}`
  return dayKey
}

// 本地日期字符串（快捷区间用；同样禁用 toISOString）
export function opLocalDate(d) {
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

// ============ 导出 CSV ============
// 一行一事件（不是一会话一行）：CSV 是给表格工具读的，嵌套的会话结构在那里表达不出来。
// 列顺序即阅读顺序：谁 → 何时 → 做了什么 → 成没成 → 从哪来。
const CSV_HEADERS = ['时间', '操作者', '角色', '分类', '动作', '结果', '来源 IP', '事由', '变更明细']

// 变更明细压成一列文本：「额度 100 → 150；状态 启用 → 禁用」
function changesText(row) {
  const list = row && row.detail && row.detail.changes
  if (!Array.isArray(list) || !list.length) return ''
  return list
    .map((c) => `${opFieldLabel(c.field)} ${opFieldValue(c.field, c.from)} → ${opFieldValue(c.field, c.to)}`)
    .join('；')
}

// 含逗号/引号/换行的单元格必须整体加引号，内部引号翻倍；
// 前缀 BOM + CRLF 行尾是为了让 Excel 直接认出 UTF-8 与换行，否则中文会变乱码。
function csvCell(v) {
  const s = v === null || v === undefined ? '' : String(v)
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function buildOpCsv(rows) {
  const lines = [CSV_HEADERS.join(',')]
  for (const row of rows || []) {
    lines.push([
      row.createdAt || '',
      row.username || '系统',
      opRoleLabel(row.role),
      opCategoryMeta(row.category).label,
      opActionMeta(row.action).label,
      opResultMeta(row.result).label,
      row.ip || '',
      row.summary || '',
      changesText(row),
    ].map(csvCell).join(','))
  }
  return `\ufeff${lines.join('\r\n')}\r\n`
}

