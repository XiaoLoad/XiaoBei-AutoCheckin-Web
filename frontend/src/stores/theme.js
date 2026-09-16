// 主题状态（Pinia）：管理全局主题的**两条轴**、GSAP 色彩补间与持久化。
//   - 色相轴：src/config/themePalette.js 定义色板，tailwindcss-themer 生成 CSS 变量
//     （--colors-brand / -brand-dark / -brand-light / -brand-ink / -surface / -card / -panel），
//     切换的收尾动作是给 <html> 挂/摘主题 class，其余由 CSS 级联完成。
//   - 明暗轴：mode 三态（auto/light/dark），收尾动作是给 <html> 挂 data-mode。
//     深色值定义在 assets/main.css，本 store 不持有任何色值。
//
// ⚠️补间取值的唯一事实源是 CSS 而不是色板：色板只覆盖 6 个色相变量，
//   而明暗切换会改动十几个令牌（含 ink/cloud/elevated/语义色）。逐个硬编码字段名
//   迟早漏掉新令牌（症状：表面在流动、文字硬切）。故这里统一按变量名清单读计算值，
//   新增令牌只需往 TWEEN_VARS 加一个名字。
// 图表（ECharts）走 canvas 渲染、不解析 CSS 变量，故另有一层 chart 取色（读计算样式真值）。
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { gsap } from 'gsap'
import { DEFAULT_THEME_ID, THEME_PALETTE, THEME_STORAGE_KEY } from '@/config/themePalette'

// 明暗模式持久化键；auto = 跟随系统（默认）
export const MODE_STORAGE_KEY = 'xb_mode'
export const DEFAULT_MODE = 'auto'
const MODES = ['auto', 'light', 'dark']

// 系统级减弱动效偏好：开启时切换退化为瞬时换肤
const REDUCED_MOTION =
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

// 补间期间挂在 <html> 上的标记类（规则见 assets/main.css）：
// 补间每帧改写 --colors-*，带 transition 的元素会每帧重启过渡、颜色永远追不上补间值，
// 于是落后于无过渡的兄弟元素——最直观的症状是目录定位条与它的文字标签脱同步、看着在闪。
const TWEENING_CLASS = 'is-theme-tweening'

// 参与补间的变量（不含 -soft 档：用量极少且只做浅底，硬切看不出）
// ⚠️新增颜色令牌时把它加进来，否则切换时该令牌会被硬切。
const TWEEN_VARS = [
  'brand', 'brand-dark', 'brand-light', 'brand-ink', 'brand-ink-strong',
  'surface', 'card', 'panel', 'elevated', 'cloud',
  'ink', 'ink-soft', 'ink-muted', 'paper',
  'amber', 'success', 'warning', 'danger', 'info'
]

function isValidId(id) {
  return THEME_PALETTE.some((t) => t.id === id)
}

// 'r g b' → [r, g, b] 数值
function tripletChannels(str) {
  return String(str)
    .trim()
    .split(/\s+/)
    .map((v) => Number(v) || 0)
}

// hex（#rgb / #rrggbb）或 rgb() 串 + alpha → rgba() 串。
// 图表要的浅填充与发光都是半透明，而令牌真值是实色，故在 JS 侧补 alpha。
export function withAlpha(color, a) {
  const s = String(color).trim()
  let r, g, b
  if (s.startsWith('#')) {
    const hex = s.slice(1)
    const full = hex.length === 3 ? hex.split('').map((c) => c + c).join('') : hex
    const n = parseInt(full, 16)
    if (Number.isNaN(n)) return s
    r = (n >> 16) & 255
    g = (n >> 8) & 255
    b = n & 255
  } else {
    const m = s.match(/(\d+)\D+(\d+)\D+(\d+)/)
    if (!m) return s
    r = Number(m[1])
    g = Number(m[2])
    b = Number(m[3])
  }
  return `rgba(${r}, ${g}, ${b}, ${a})`
}

const media = typeof window !== 'undefined' && window.matchMedia
  ? window.matchMedia('(prefers-color-scheme: dark)')
  : null

function restoreTheme() {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY)
    return isValidId(saved) ? saved : DEFAULT_THEME_ID
  } catch {
    /* 隐私模式等 storage 不可用时回退默认主题 */
    return DEFAULT_THEME_ID
  }
}

function restoreMode() {
  try {
    const saved = localStorage.getItem(MODE_STORAGE_KEY)
    return MODES.includes(saved) ? saved : DEFAULT_MODE
  } catch {
    return DEFAULT_MODE
  }
}

// 图表分类色板：浅色用 600 档原值；深色统一提到 400 档——600 档压在深色底上会糊成
// 一片，400 档对最亮表面最低 3.2:1，作为图形色足够。
const CATEGORICAL = {
  light: ['#dc2626', '#d97706', '#2563eb', '#7c3aed', '#0891b2', '#65a30d', '#db2777', '#9ca3af'],
  dark: ['#f87171', '#fbbf24', '#60a5fa', '#a78bfa', '#22d3ee', '#a3e635', '#f472b6', '#94a3b8']
}

// 一次性取计算结果样式，供下面各档取色（避免每个色值各查一遍）。
// 非浏览器环境（SSR、单测）没有计算样式：退成全黑，至少不炸；浏览器里永远走真值路径。
function chartColors(meta, dark) {
  const cs = typeof document === 'undefined' ? null : getComputedStyle(document.documentElement)
  const triplet = (name) => {
    if (!cs) return [0, 0, 0]
    const [r, g, b] = tripletChannels(cs.getPropertyValue('--colors-' + name))
    return [r || 0, g || 0, b || 0]
  }
  const solid = (name) => {
    const [r, g, b] = triplet(name)
    return `rgb(${r}, ${g}, ${b})`
  }
  const alpha = (name, a) => {
    const [r, g, b] = triplet(name)
    return `rgba(${r}, ${g}, ${b}, ${a})`
  }
  return {
    // 中性层
    ink: solid('ink-muted'),        // 轴标签、图例文字
    grid: alpha('ink', 0.1),        // 网格线
    axis: alpha('ink', 0.12),       // 轴线
    ring: alpha('ink', 0.16),       // 圆环刻度圈
    ringTrack: alpha('ink', 0.08),  // 圆环轨道
    border: solid('elevated'),      // 饼/环扇区分隔边，取所在层底色
    neutral: solid('neutral'),      // 中性档（未使用/其它）
    // 数据色：brand 走文字档，浅色下与 brand 同值、深色下自动换成提亮档
    brand: solid('brand-ink'),
    brandLight: solid('brand-light'),
    success: solid('success'),
    warning: solid('warning'),
    amber: solid('amber'),
    danger: solid('danger'),
    info: solid('info'),
    // 活动签到系列：默认等于 info（与活动徽标同色），深色下同样跟随 info 提亮；
    // brand 与 info 撞色而单独覆盖过 activity 的主题（teal）须自带 activityDark
    activity: dark ? meta.activityDark || solid('info') : meta.activity,
    categorical: dark ? CATEGORICAL.dark : CATEGORICAL.light
  }
}

// auto → 交给系统偏好；其余原样返回。对外只暴露「实际生效」的 light/dark
function resolveMode(mode) {
  if (mode === 'light' || mode === 'dark') return mode
  return media && media.matches ? 'dark' : 'light'
}

function applyThemeClass(id) {
  const root = document.documentElement
  for (const t of THEME_PALETTE) {
    if (t.cls) root.classList.remove(t.cls)
  }
  const target = THEME_PALETTE.find((t) => t.id === id)
  if (target?.cls) root.classList.add(target.cls)
}

export const useThemeStore = defineStore('theme', () => {
  const current = ref(restoreTheme())
  const mode = ref(restoreMode())

  // 当前色相主题元信息（label / 各色 hex）。图表取色不要用这里的 hex——那是色相轴的
  // 原始值、不随明暗走，一律改用下面的 chart。
  const meta = computed(() => THEME_PALETTE.find((t) => t.id === current.value) || THEME_PALETTE[0])
  // 实际生效的明暗（auto 时取系统偏好），模板里的开关选中态与图标按它渲染
  const resolvedMode = computed(() => resolveMode(mode.value))
  const isDark = computed(() => resolvedMode.value === 'dark')

  // 进行中的补间：再次切换时 kill 续接
  let activeTween = null

  function clearInlineVars() {
    const style = document.documentElement.style
    for (const name of TWEEN_VARS) {
      style.removeProperty('--colors-' + name)
    }
  }

  // 读 <html> 上这些变量的当前计算值（三元组数组）
  function readVars() {
    const cs = getComputedStyle(document.documentElement)
    const out = []
    for (const name of TWEEN_VARS) {
      out.push(...tripletChannels(cs.getPropertyValue('--colors-' + name)))
    }
    return out
  }

  // ===== 图表用色 =====
  // ECharts 走 canvas 渲染、不解析 CSS 变量，必须读出计算样式真值再拼成 rgb()/rgba()。
  // chart 依赖 current + resolvedMode，切色相或切明暗后重新求值；此刻补间还没写入
  // 内联变量（GSAP 要到下一帧才 onUpdate），读到的是目标 class 的值，图表随之硬切到位
  // ——与画布本就不参与逐帧插值是一致的。
  const chart = computed(() => {
    // 显式建依赖：值出自 getComputedStyle，光靠它追踪不到响应式变化
    void current.value
    void resolvedMode.value
    return chartColors(meta.value, isDark.value)
  })

  function applyMode(m) {
    document.documentElement.dataset.mode = resolveMode(m)
  }

  // 全局色彩补间：在 :root 内联变量上从旧值渐变到目标值（内联样式优先级高于
  // class 变量，补间期间全站颜色连续流动），完成后清内联、交还 class 变量接管。
  //
  // ⚠️取值顺序不能换：
  //   ① 先读 from —— 此刻 <html> 上还是旧 class/旧 data-mode；若上一段补间仍在跑，
  //      读到的就是它的内联中间值，天然续接，不需要额外记录起点。
  //   ② 再 kill 补间并清内联 —— 不清的话，内联值会盖住接下来挂上的新 class，
  //      导致 to 读到的还是旧值，补间原地踏步（视觉上退化成瞬间切换）。
  //   ③ 挂新 class / data-mode 之后读 to。
  function tweenTo(apply) {
    const root = document.documentElement
    const fromChannels = readVars()

    activeTween?.kill()
    activeTween = null
    clearInlineVars()

    apply()
    const toChannels = readVars()

    if (REDUCED_MOTION || fromChannels.length !== toChannels.length) {
      root.classList.remove(TWEENING_CLASS)
      return
    }

    const same = fromChannels.every((v, i) => v === toChannels[i])
    if (same) return

    root.classList.add(TWEENING_CLASS)
    const proxy = {}
    const toProps = {}
    fromChannels.forEach((v, i) => {
      proxy['c' + i] = v
      toProps['c' + i] = toChannels[i]
    })

    activeTween = gsap.to(proxy, {
      ...toProps,
      duration: 0.6,
      ease: 'none',
      onUpdate: () => {
        for (let i = 0; i < TWEEN_VARS.length; i++) {
          const r = Math.round(proxy['c' + (i * 3)])
          const g = Math.round(proxy['c' + (i * 3 + 1)])
          const b = Math.round(proxy['c' + (i * 3 + 2)])
          root.style.setProperty('--colors-' + TWEEN_VARS[i], `${r} ${g} ${b}`)
        }
      },
      onComplete: () => {
        activeTween = null
        root.classList.remove(TWEENING_CLASS)
        // 目标 class 已挂、其变量值与补间终值一致，清内联无缝交还
        clearInlineVars()
      }
    })
  }

  // 切换色相：class 与 localStorage 立即生效（持久真相），视觉上由补间线性流动到位
  function setTheme(id) {
    if (!isValidId(id) || current.value === id) return
    current.value = id
    try {
      localStorage.setItem(THEME_STORAGE_KEY, id)
    } catch {
      /* storage 不可用时主题仅本次会话生效 */
    }
    tweenTo(() => applyThemeClass(id))
  }

  // 切换明暗：与切色相同一条补间通道，故「换色相 + 换明暗」先后触发时会自然衔接
  function setMode(m) {
    if (!MODES.includes(m) || mode.value === m) return
    mode.value = m
    try {
      localStorage.setItem(MODE_STORAGE_KEY, m)
    } catch {
      /* 同上 */
    }
    tweenTo(() => applyMode(m))
  }

  // 三态循环（供按钮用）：auto → light → dark → auto
  function cycleMode() {
    setMode(MODES[(MODES.indexOf(mode.value) + 1) % MODES.length])
  }

  // 系统偏好变化：只在 auto 下跟随（手动选定后不夺走控制权）
  function onSystemChange() {
    if (mode.value !== 'auto') return
    tweenTo(() => applyMode('auto'))
  }
  if (media) {
    if (media.addEventListener) media.addEventListener('change', onSystemChange)
    else if (media.addListener) media.addListener(onSystemChange)
  }

  // 兜底：index.html 首帧脚本负责防闪色，这里在 store 初始化时再对齐一次（幂等）
  applyThemeClass(current.value)
  applyMode(mode.value)

  return {
    current, mode, resolvedMode, isDark, meta, chart,
    setTheme, setMode, cycleMode
  }
})
