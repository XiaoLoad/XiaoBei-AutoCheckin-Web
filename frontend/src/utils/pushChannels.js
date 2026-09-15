// 推送通道的展示元信息：通道标识 → 文案 / 缩写 / 色调。
// 凭证池、配置套推送、账号推送绑定三处共用，避免同一通道在不同页面叫法或配色不一致。
export const PUSH_CHANNELS = ['serverchan', 'pushplus', 'email']

export const CHANNEL_META = {
  serverchan: { label: 'Server 酱', short: 'SC', tone: 'bg-brand/10 text-brand', dot: 'bg-brand' },
  pushplus: { label: 'PushPlus', short: 'PP', tone: 'bg-success/10 text-success', dot: 'bg-success' },
  email: { label: '邮箱', short: '@', tone: 'bg-info/10 text-info', dot: 'bg-info' }
}

const UNKNOWN = { label: '未知通道', short: '··', tone: 'bg-ink/10 text-ink-soft', dot: 'bg-ink/30' }

export function channelMeta(ch) {
  return CHANNEL_META[ch] || { ...UNKNOWN, label: ch || UNKNOWN.label }
}

export const channelLabel = (ch) => channelMeta(ch).label
export const channelShort = (ch) => channelMeta(ch).short
export const channelTone = (ch) => channelMeta(ch).tone
export const channelDot = (ch) => channelMeta(ch).dot

// ---- 账号级推送绑定项：形态归一 ----
// 后端按内容取最简写法存：12 / {credId:12, to:'a@x.com'} / {to:'a@x.com'}。
// 编辑器统一成 {credId, to}，模板里就不用到处判断两种形态。
export function readCredEntry(raw) {
  if (raw && typeof raw === 'object') {
    const cid = Number(raw.credId)
    return {
      credId: Number.isInteger(cid) && cid > 0 ? cid : null,
      to: typeof raw.to === 'string' ? raw.to : ''
    }
  }
  const cid = Number(raw)
  return { credId: Number.isInteger(cid) && cid > 0 ? cid : null, to: '' }
}

export function normalizePushCreds(raw) {
  const out = {}
  for (const ch of PUSH_CHANNELS) out[ch] = readCredEntry((raw || {})[ch])
  return out
}

// 只有邮件通道有「收件人」概念，其余通道带 to 会被后端判为脏数据（4105）
export const RECIPIENT_CHANNELS = ['email']

// 编辑器态 → 接口形态：没内容的通道不落键；收件人只在非空且通道支持时随项写入
export function serializePushCreds(form) {
  const out = {}
  for (const ch of PUSH_CHANNELS) {
    const { credId, to } = (form || {})[ch] || {}
    const recip = RECIPIENT_CHANNELS.includes(ch) ? to : ''
    if (credId && recip) out[ch] = { credId, to: recip }
    else if (credId) out[ch] = credId
    else if (recip) out[ch] = { to: recip }
  }
  return out
}

// 有「自己的推送目标」的通道：绑了凭证，或单独指定了收件人
export function activeChannels(raw) {
  return PUSH_CHANNELS.filter((ch) => {
    const e = readCredEntry((raw || {})[ch])
    return !!(e.credId || e.to)
  })
}
