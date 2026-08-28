// 定时调度相关的纯计算工具（前端框架阶段，无后端）。
// 明确区分两层时间：
//   - 业务层：配置套 time（startHour/endHour/weekdays/randomDelayMax）——"这次签到长什么样"
//   - 调度层：定时任务的"何时触发"。默认跟随配置套（在配置套星期 + startHour 触发，带抖动），
//     仅"自定义"模式才独立设定 HH:mm。两者之间不冲突、可独立覆盖。

export const WEEKDAY_LABELS = ['一', '二', '三', '四', '五', '六', '日']
export const WEEKDAY_FULL = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

export const pad = (n) => String(n).padStart(2, '0')

// 把 [1..7] 星期数组渲染成"周一~周日 / 周一、周三、周五"之类紧凑文案
export function weekdayRangeText(wd) {
  const arr = (wd || []).slice().sort((a, b) => a - b)
  if (arr.length === 0) return '未选择'
  if (arr.length === 7) return '一至周日'
  // 连续段合并：如 [1,2,3] → "周一~周三"
  const segs = []
  let start = arr[0]
  let prev = arr[0]
  for (let i = 1; i <= arr.length; i++) {
    const cur = arr[i]
    if (cur === prev + 1) {
      prev = cur
      continue
    }
    segs.push(start === prev ? WEEKDAY_FULL[start - 1] : `${WEEKDAY_FULL[start - 1]}~${WEEKDAY_FULL[prev - 1]}`)
    start = cur
    prev = cur
  }
  return segs.join('、')
}

// 计算下一次执行时间（返回 Date 或 null）。
// mode: 'follow' | 'custom'；custom: {hour,minute,weekdays,randomDelayMax}；
// configMeta: 配置套元信息（含 time），用于 follow 模式的星期与起始小时。
export function computeNextRun(mode, custom, configMeta) {
  const now = new Date()
  // follow / standalone 均从配置元信息（time.weekdays / time.signTime）读取触发时刻；custom 用自身 hour/minute
  const wd = mode === 'custom' ? custom?.weekdays || [] : configMeta?.time?.weekdays || []
  if (!wd.length) return null
  // follow / standalone 采纳配置元信息的「定时签到时间」(signTime，精确到时分)；custom 模式用自身 hour/minute
  const hour = mode === 'custom' ? custom?.hour ?? 8 : configMeta?.time?.signTime?.hour ?? configMeta?.time?.startHour ?? 8
  const minute = mode === 'custom' ? custom?.minute ?? 0 : configMeta?.time?.signTime?.minute ?? 0
  for (let d = 0; d <= 14; d++) {
    const cand = new Date(now)
    cand.setDate(now.getDate() + d)
    cand.setHours(hour, minute, 0, 0)
    const jsDay = cand.getDay() // 0=周日 … 6=周六
    const ourDay = jsDay === 0 ? 7 : jsDay
    if (!wd.includes(ourDay)) continue
    // 今天的时刻若已经过去，则从明天起算
    if (d === 0 && cand.getTime() <= now.getTime()) continue
    return cand
  }
  return null
}

// 把 Date 渲染成"今天/明天/周X HH:mm"
export function formatNextRun(date) {
  if (!date) return { rel: '—', weekday: '—', time: '—', text: '暂不可执行' }
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const diffDays = Math.round((new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime() - startOfToday) / 86400000)
  const rel = diffDays === 0 ? '今天' : diffDays === 1 ? '明天' : WEEKDAY_FULL[date.getDay() === 0 ? 6 : date.getDay() - 1]
  const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`
  return { rel, weekday: WEEKDAY_FULL[date.getDay() === 0 ? 6 : date.getDay() - 1], time, text: `${rel} ${time}` }
}

// 模式摘要文案（卡片 chip / 抽屉预览使用）
export function nextRunSummary(mode, custom, configMeta) {
  const jitter = (n) => (n ? `（随机±${n}分）` : '')
  if (mode !== 'custom') {
    const wd = configMeta?.time?.weekdays || []
    const st = configMeta?.time?.signTime || { hour: 8, minute: 0 }
    const j = configMeta?.time?.randomDelayMax ?? 0
    const prefix = mode === 'standalone' ? '本任务配置' : '跟随配置套'
    return `${prefix}：每周${weekdayRangeText(wd)} ${pad(st.hour)}:${pad(st.minute)} 起${jitter(j)}`
  }
  const wd = custom?.weekdays || []
  return `自定义：每周${weekdayRangeText(wd)} ${pad(custom?.hour ?? 8)}:${pad(custom?.minute ?? 0)}${jitter(custom?.randomDelayMax)}`
}
