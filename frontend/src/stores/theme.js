// 主题状态（Pinia）：管理全局主题的切换、GSAP 色彩补间与持久化。
// 色值本体定义在 src/config/themePalette.js；CSS 变量由 tailwindcss-themer 生成
// （--colors-brand / -brand-dark / -brand-light / -surface / -card / -panel）。
// 切换的收尾动作是给 <html> 挂/摘主题 class，其余全部由 CSS 级联完成。
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { gsap } from 'gsap'
import { DEFAULT_THEME_ID, THEME_PALETTE, THEME_STORAGE_KEY } from '@/config/themePalette'

// 系统级减弱动效偏好：开启时切换退化为瞬时换肤
const REDUCED_MOTION =
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

// 补间期间挂在 <html> 上的标记类（规则见 assets/main.css）：
// 补间每帧改写 --colors-*，带 transition 的元素会每帧重启过渡、颜色永远追不上补间值，
// 于是落后于无过渡的兄弟元素——最直观的症状是目录定位条与它的文字标签脱同步、看着在闪。
const TWEENING_CLASS = 'is-theme-tweening'

// 参与补间的主题变量：色板字段 → --colors- 后缀（与 tailwindcss-themer 命名规则一致）
const THEMED_VARS = [
  { field: 'brand', suffix: 'brand' },
  { field: 'dark', suffix: 'brand-dark' },
  { field: 'light', suffix: 'brand-light' },
  { field: 'surface', suffix: 'surface' },
  { field: 'card', suffix: 'card' },
  { field: 'panel', suffix: 'panel' },
]

function isValidId(id) {
  return THEME_PALETTE.some((t) => t.id === id)
}

// '#rrggbb' → 'r g b' 三元组字符串（CSS 变量的存储形态）
function hexToTriplet(hex) {
  const n = parseInt(hex.slice(1), 16)
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`
}

// 'r g b' → [r, g, b] 数值
function tripletChannels(str) {
  return String(str)
    .trim()
    .split(/\s+/)
    .map((v) => Number(v) || 0)
}

function restore() {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY)
    return isValidId(saved) ? saved : DEFAULT_THEME_ID
  } catch {
    /* 隐私模式等 storage 不可用时回退默认主题 */
    return DEFAULT_THEME_ID
  }
}

function applyToRoot(id) {
  const root = document.documentElement
  for (const t of THEME_PALETTE) {
    if (t.cls) root.classList.remove(t.cls)
  }
  const target = THEME_PALETTE.find((t) => t.id === id)
  if (target?.cls) root.classList.add(target.cls)
}

export const useThemeStore = defineStore('theme', () => {
  const current = ref(restore())

  // 当前主题元信息（label/各色 hex 等），供图表 tooltip 等 JS 消费方取色
  const meta = computed(() => THEME_PALETTE.find((t) => t.id === current.value) || THEME_PALETTE[0])
  const brandHex = computed(() => meta.value.brand)
  // 图表「活动签到」系列用色，随主题切换（见 themePalette 注释）
  const activityHex = computed(() => meta.value.activity)

  // 进行中的补间：再次切换时 kill 并以其内联值（补间中间态）为新起点，天然衔接
  let activeTween = null

  function clearInlineVars() {
    const style = document.documentElement.style
    for (const { suffix } of THEMED_VARS) {
      style.removeProperty('--colors-' + suffix)
    }
  }

  // 全局色彩补间：在 :root 内联变量上从旧主题值渐变到目标值（内联样式优先级高于
  // class 变量，补间期间全站颜色连续流动），完成后清内联、交还 class 变量接管。
  function tweenToTheme(fromMeta, target) {
    const root = document.documentElement
    root.classList.add(TWEENING_CLASS)
    const computedStyle = getComputedStyle(root)
    const fromChannels = []
    const toChannels = []

    for (const { field, suffix } of THEMED_VARS) {
      // 补间起点：上一次补间仍在进行时取内联中间值续接；否则取切换前主题的色板值。
      // 不能读计算值——目标 class 已在 setTheme 中挂上，计算值此刻已是终点，
      // 起点若等于终点，补间将原地踏步、视觉上退化为瞬间切换。
      const fromStr = activeTween
        ? computedStyle.getPropertyValue('--colors-' + suffix)
        : hexToTriplet(fromMeta[field])
      fromChannels.push(...tripletChannels(fromStr))
      toChannels.push(...tripletChannels(hexToTriplet(target[field])))
    }

    // 代理对象持 18 个数值通道，GSAP 对数值插值，onUpdate 重组三元组写入变量
    const proxy = {}
    const toProps = {}
    fromChannels.forEach((v, i) => {
      proxy['c' + i] = v
      toProps['c' + i] = toChannels[i]
    })

    activeTween?.kill()
    activeTween = gsap.to(proxy, {
      ...toProps,
      duration: 0.6,
      ease: 'none',
      onUpdate: () => {
        for (let i = 0; i < THEMED_VARS.length; i++) {
          const { suffix } = THEMED_VARS[i]
          const r = Math.round(proxy['c' + (i * 3)])
          const g = Math.round(proxy['c' + (i * 3 + 1)])
          const b = Math.round(proxy['c' + (i * 3 + 2)])
          root.style.setProperty('--colors-' + suffix, `${r} ${g} ${b}`)
        }
      },
      onComplete: () => {
        activeTween = null
        root.classList.remove(TWEENING_CLASS)
        // 目标 class 已挂、其变量值与补间终值一致，清内联无缝交还
        clearInlineVars()
      },
    })
  }

  // 切换主题：class 与 localStorage 立即生效（持久真相），视觉上由补间线性流动到位
  function setTheme(id) {
    if (!isValidId(id) || current.value === id) return
    // 先记录切换前主题作为补间起点（必须在挂 class 之前）
    const prevMeta = meta.value
    current.value = id
    applyToRoot(id)
    try {
      localStorage.setItem(THEME_STORAGE_KEY, id)
    } catch {
      /* storage 不可用时主题仅本次会话生效 */
    }
    const target = THEME_PALETTE.find((t) => t.id === id)
    if (target && !REDUCED_MOTION) {
      tweenToTheme(prevMeta, target)
    } else {
      // 瞬时换肤：一并摘掉可能残留的补间标记，避免过渡被永久压成 0
      document.documentElement.classList.remove(TWEENING_CLASS)
      clearInlineVars()
    }
  }

  // 兜底：index.html 首帧脚本负责防闪色，这里在 store 初始化时再对齐一次（幂等）
  applyToRoot(current.value)

  return { current, meta, brandHex, activityHex, setTheme }
})
