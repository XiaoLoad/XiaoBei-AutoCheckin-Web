// 推送落位核对：口径对齐后端 services/scheduler._resolve_push_creds——
// 账号自带凭证优先，该账号没绑的通道回落配置套 push.credIds，两处都空则该通道本次跳过。
// 账号绑定（accounts[].pushCreds）与凭证池都已在 store 里，本地即可算准，不必为统计再开接口。
import { readCredEntry } from './pushChannels'

export function accountCredId(account, ch) {
  return readCredEntry((account.pushCreds || {})[ch]).credId || 0
}

/** 账号在指定通道自填的收件邮箱（只有邮件通道有） */
export function accountRecipient(account, ch) {
  return readCredEntry((account.pushCreds || {})[ch]).to
}

/** 凭证里的默认收件人。emailTo 不在后端脱敏字段内，池里拿到的是真值 */
export function emailToOf(cred) {
  return ((cred && cred.fields && cred.fields.emailTo) || '').trim()
}

const joinNames = (names, cap = 3) =>
  names.length <= cap
    ? names.join('、')
    : `${names.slice(0, cap).join('、')} 等 ${names.length} 个`

/**
 * token 型通道（Server 酱 / PushPlus）：只问「谁没绑」。
 * 三态：ok 全绑好 / warn 有漏网但兜底接得住 / gap 有漏网且会跳过。
 */
export function auditTokenChannel(ch, accounts, fallbackCred) {
  if (!accounts.length) return { state: 'idle', text: '暂无账号', detail: '' }
  const unbound = accounts.filter((a) => !accountCredId(a, ch)).map((a) => a.name)
  if (!unbound.length) return { state: 'ok', text: '全部已绑定', detail: '', leak: false, unbound: [] }
  return {
    state: fallbackCred ? 'warn' : 'gap',
    text: `${unbound.length} 个未绑`,
    detail: `未绑：${joinNames(unbound)}`,
    leak: true,
    unbound
  }
}

/**
 * 单账号视角的同一条判断：只看这一个账号。
 * 账号绑了凭证但凭证已删/停用时不回落兜底（后端直接跳过），这一态必须说清，
 * 且不能给兜底入口——给了也救不回来。
 */
export function auditAccountChannel(ch, account, fallbackCred, credById) {
  if (!account) return { state: 'idle', text: '未选账号', detail: '' }
  const ownId = accountCredId(account, ch)
  const own = ownId ? credById(ownId) : null
  if (own) return { state: 'ok', text: '已绑定', detail: `用「${own.name}」发送`, leak: false }
  if (ownId) {
    return { state: 'gap', text: '凭证已失效', detail: '账号绑定的凭证不存在或已停用，本通道会跳过', leak: false, dangling: true }
  }
  if (fallbackCred) {
    return { state: 'warn', text: '未绑定', detail: `由兜底「${fallbackCred.name}」代发`, leak: true }
  }
  return { state: 'gap', text: '未绑定', detail: '未设兜底，本通道会跳过', leak: true }
}

/**
 * 邮件通道：账号之间的差异只在收件邮箱（账号自填 > 所用凭证的默认收件邮箱），
 * 故这里算的是「每个账号实际发给谁」，而不是谁绑没绑凭证。
 * src：account 账号自填 / own-cred 账号自带凭证 / shared-cred 套级共用凭证 / none 发不出去。
 */
export function auditEmailChannel(accounts, fallbackCred, credById) {
  const rows = accounts.map((a) => {
    const ownId = accountCredId(a, 'email')
    const ownCred = ownId ? credById(ownId) : null
    // 账号绑了凭证但凭证没了 —— 后端不回落到套级凭证，直接判空
    const dangling = !!ownId && !ownCred
    const sender = dangling ? null : ownCred || fallbackCred
    const ownTo = accountRecipient(a, 'email')
    const to = sender ? ownTo || emailToOf(sender) : ''
    return {
      id: a.id,
      name: a.name,
      to,
      senderName: sender ? sender.name : '',
      ownSender: !dangling && !!ownCred,
      src: !sender ? 'none' : ownTo ? 'account' : ownCred ? 'own-cred' : 'shared-cred'
    }
  })
  const missing = rows.filter((r) => !r.to).map((r) => r.name)
  const ownSenderCount = rows.filter((r) => r.ownSender).length
  const base = {
    rows,
    missing,
    sharedTo: emailToOf(fallbackCred),
    senderName: fallbackCred ? fallbackCred.name : '',
    senderId: fallbackCred ? fallbackCred.id : '',
    ownSenderCount,
    // 还有账号要靠套级凭证发送时才需要「发件凭证」槽，否则各账号自带、无需指定
    needsSender: ownSenderCount < rows.length,
    ownRecipientCount: rows.filter((r) => r.src === 'account').length
  }
  if (!rows.length) return { ...base, state: 'idle', text: '暂无账号', detail: '' }
  if (missing.length) {
    return {
      ...base,
      state: 'gap',
      text: `${missing.length} 个发不出去`,
      detail: fallbackCred
        ? `未送达：${joinNames(missing)}（既没自填收件邮箱，所用凭证也没填默认收件邮箱）`
        : `未送达：${joinNames(missing)}（未指定共用发件凭证）`
    }
  }
  return {
    ...base,
    state: 'ok',
    text: '全部可送达',
    detail: base.needsSender
      ? base.sharedTo
        ? `默认收件邮箱 ${base.sharedTo}`
        : ''
      : '各账号自带邮件凭证，无需共用发件凭证'
  }
}

/** 单账号视角的邮件落点 */
export function auditAccountEmail(account, fallbackCred, credById) {
  if (!account) return { state: 'idle', text: '未选账号', detail: '', to: '', src: 'none' }
  const ownId = accountCredId(account, 'email')
  const ownCred = ownId ? credById(ownId) : null
  const dangling = !!ownId && !ownCred
  const sender = dangling ? null : ownCred || fallbackCred
  const ownTo = accountRecipient(account, 'email')
  const to = sender ? ownTo || emailToOf(sender) : ''
  const src = !sender ? 'none' : ownTo ? 'account' : ownCred ? 'own-cred' : 'shared-cred'
  const base = { to, src, senderName: sender ? sender.name : '', senderId: sender ? sender.id : '', ownSender: !dangling && !!ownCred, rows: [] }
  if (dangling) return { ...base, state: 'gap', text: '凭证已失效', detail: '账号绑定的邮件凭证不存在或已停用，本通道会跳过', needsSender: false }
  if (!sender) return { ...base, state: 'gap', text: '未指定发件凭证', detail: '本通道会跳过', needsSender: true }
  if (!to) return { ...base, state: 'gap', text: '没有收件邮箱', detail: '账号没自填，所用凭证也没填默认收件邮箱，本通道会跳过', needsSender: true }
  return { ...base, state: 'ok', text: '会送达', detail: '', needsSender: !ownCred }
}
