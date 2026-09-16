// 主题色板单一事实源（**色相轴**）：tailwind.config.js（tailwindcss-themer 生成 CSS 变量）、
// stores/theme.js（切换、补间与持久化）、设置页/侧边栏切换 UI 共用这一份定义。
//
// 明暗是**另一条独立的轴**，不进这个文件：深色值（各主题的染色表面、brand 提亮档、
// 中性文字与语义色）全部定义在 assets/main.css 的 html[data-mode="dark"] 各块里，
// 由 <html> 上的 data-mode 属性切换，与本文件的色相 class 互不干扰。
// 新增主题时除了在下面加一项，还要在 main.css 里补一条 html.theme-<id>[data-mode="dark"]。
//
// - id：主题标识，持久化到 localStorage（THEME_STORAGE_KEY）；
// - cls：启用主题时挂到 <html> 上的 class，与 tailwindcss-themer 的主题名一致
//   （插件按主题名生成同名 class 选择器）；默认主题不挂 class（插件 :root 即默认）；
//   index.html 首帧脚本按「theme- + id」约定恢复非默认主题，新增主题请沿用该命名；
// - 颜色令牌（均按「白底文本对比度 ≥ 4.5:1」与同色系和谐挑选）：
//     brand / dark / light —— 品牌强调三档。brand 是**填充档**，必须压得住白字
//       （六套里只有 ocean 的 #1674f8 不达标，已压暗为 #1266e2：白字 4.30 → 5.22）；
//     brandInk / brandInkStrong —— brand 的**文字专用档与它的 hover 加深档**。
//       填充要压得住白字（得偏暗）、文字要压在浅底或深底上都达标（浅色下得够深、
//       深色下得够亮），一个色值不可能同时满足，故拆成两个变量（--colors-brand 与
//       --colors-brand-ink），textColor 指向后者，调用点零改动。
//       ⚠️ 文字档要按**自身 /10 淡底**而不是纯白来定：头像、徽标这类 `bg-brand/10
//       text-brand` 的写法处处都是，压在淡底上比压在白底上低 0.5 左右（实测拿
//       brand 原值当文字档时，这批元素只剩 3.96~4.43）。故文字档统一取同色系的深档。
//       deep 档（strong）必须仍比 DEFAULT 更深，否则 hover:text-brand-dark 没有反馈。
//       深色下由 main.css 各块整体覆盖成亮色档；
//     surface —— 页面底色（布局根、body 兜底底色）；深色下 = 本主题 panel 提亮 5.5%；
//     card    —— 卡片底色（微染近白，dash-card 等页面卡片）；深色下 = panel 提亮 10.5%；
//     panel   —— 深色面板（侧边栏、系统信息横幅、登录品牌区）。它是深色下的**层次锚点**：
//                侧栏保持本值最深，页面底/卡片/浮层依次向白提亮，故「弹窗与下拉保持
//                更亮一档」的层次在深色下依然成立；
//     activity —— 图表「活动签到」系列用色，默认取 info 令牌值（#0ea5e9）以与活动徽标同色；
//                  仅当本主题 brand 与 info 色相撞车、饼图两瓣分不出来时才覆盖（见 teal），
//                  覆盖值的唯一约束是与本主题 brand 拉开色相；
//     activityDark —— 覆盖过 activity 的主题必须同时给出深色版（未覆盖的走 info 令牌的深色值，
//                  不必写）；图表取色见 stores/theme.js 的 chart。
//   ocean 主题的三项表面值即历史现行值（cloud/白/ink），默认主题视觉零变化。
export const THEME_STORAGE_KEY = 'xb_theme'
export const DEFAULT_THEME_ID = 'ocean'

export const THEME_PALETTE = [
  {
    id: 'ocean', cls: '', label: '深海蓝',
    brand: '#1266e2', dark: '#0f5dd4', light: '#4a9aff', brandInk: '#0f5dd4', brandInkStrong: '#0a4aad',
    surface: '#EEF2F9', card: '#FFFFFF', panel: '#14213D',
    activity: '#0ea5e9',
  },
  {
    id: 'jade', cls: 'theme-jade', label: '翡翠绿',
    brand: '#047857', dark: '#065f46', light: '#34d399', brandInk: '#065f46', brandInkStrong: '#064e3b',
    surface: '#EAF3EE', card: '#FBFDFC', panel: '#0E2A22',
    activity: '#0ea5e9',
  },
  {
    id: 'violet', cls: 'theme-violet', label: '紫罗兰',
    brand: '#7c3aed', dark: '#6d28d9', light: '#a78bfa', brandInk: '#6d28d9', brandInkStrong: '#5b21b6',
    surface: '#F1EEF9', card: '#FCFBFE', panel: '#211A38',
    activity: '#0ea5e9',
  },
  {
    id: 'coral', cls: 'theme-coral', label: '珊瑚橙',
    brand: '#c2410c', dark: '#9a3412', light: '#fb923c', brandInk: '#9a3412', brandInkStrong: '#7c2d12',
    surface: '#F8F0E9', card: '#FEFBF8', panel: '#31201A',
    activity: '#0ea5e9',
  },
  {
    // brand 与 info 同属青系（#0e7490 / #0ea5e9），饼图里两瓣几乎分不出来，故活动系列改用紫
    id: 'teal', cls: 'theme-teal', label: '青碧',
    brand: '#0e7490', dark: '#155e75', light: '#22d3ee', brandInk: '#155e75', brandInkStrong: '#164e63',
    surface: '#E9F2F5', card: '#FAFCFD', panel: '#0C2733',
    activity: '#8b5cf6', activityDark: '#a78bfa',
  },
  {
    id: 'blossom', cls: 'theme-blossom', label: '淡粉',
    brand: '#db2777', dark: '#be185d', light: '#f472b6', brandInk: '#be185d', brandInkStrong: '#9d174d',
    surface: '#FAEFF3', card: '#FDFBFC', panel: '#31121F',
    activity: '#0ea5e9',
  },
]
