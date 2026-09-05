// 主题色板单一事实源：tailwind.config.js（tailwindcss-themer 生成 CSS 变量）与
// stores/theme.js（切换、补间与持久化）、设置页/侧边栏切换 UI 共用这一份定义。
//
// - id：主题标识，持久化到 localStorage（THEME_STORAGE_KEY）；
// - cls：启用主题时挂到 <html> 上的 class，与 tailwindcss-themer 的主题名一致
//   （插件按主题名生成同名 class 选择器）；默认主题不挂 class（插件 :root 即默认）；
//   index.html 首帧脚本按「theme- + id」约定恢复非默认主题，新增主题请沿用该命名；
// - 颜色令牌（均按「白底文本对比度 ≥ 4.5:1」与同色系和谐挑选）：
//     brand / dark / light —— 品牌强调三档（light 为预留浅色变体，当前未被组件使用）；
//     surface —— 页面底色（布局根、body 兜底底色）；
//     card    —— 卡片底色（微染近白，dash-card 等页面卡片；弹窗/下拉等浮层保持纯白形成层次）；
//     panel   —— 深色面板（侧边栏、系统信息横幅、登录品牌区）；
//     companion —— 图表系列副色（用户仪表盘「寝室打卡」等第二系列），随主题挑选、
//                  唯一约束是与本主题 brand 拉开色相，保证双系列图表可辨识；
//   ocean 主题的三项表面值即历史现行值（cloud/白/ink），默认主题视觉零变化。
export const THEME_STORAGE_KEY = 'xb_theme'
export const DEFAULT_THEME_ID = 'ocean'

export const THEME_PALETTE = [
  {
    id: 'ocean', cls: '', label: '深海蓝',
    brand: '#1674f8', dark: '#0f5dd4', light: '#4a9aff',
    surface: '#EEF2F9', card: '#FFFFFF', panel: '#14213D',
    companion: '#0ea5e9',
  },
  {
    id: 'jade', cls: 'theme-jade', label: '翡翠绿',
    brand: '#047857', dark: '#065f46', light: '#34d399',
    surface: '#EAF3EE', card: '#FBFDFC', panel: '#0E2A22',
    companion: '#0ea5e9',
  },
  {
    id: 'violet', cls: 'theme-violet', label: '紫罗兰',
    brand: '#7c3aed', dark: '#6d28d9', light: '#a78bfa',
    surface: '#F1EEF9', card: '#FCFBFE', panel: '#211A38',
    companion: '#0ea5e9',
  },
  {
    id: 'coral', cls: 'theme-coral', label: '珊瑚橙',
    brand: '#c2410c', dark: '#9a3412', light: '#fb923c',
    surface: '#F8F0E9', card: '#FEFBF8', panel: '#31201A',
    companion: '#0e7490',
  },
  {
    id: 'teal', cls: 'theme-teal', label: '青碧',
    brand: '#0e7490', dark: '#155e75', light: '#22d3ee',
    surface: '#E9F2F5', card: '#FAFCFD', panel: '#0C2733',
    companion: '#8b5cf6',
  },
  {
    id: 'blossom', cls: 'theme-blossom', label: '淡粉',
    brand: '#db2777', dark: '#be185d', light: '#f472b6',
    surface: '#FAEFF3', card: '#FDFBFC', panel: '#31121F',
    companion: '#0ea5e9',
  },
]
