/** @type {import('tailwindcss').Config} */
// TailwindCSS 配置文件
// content 指定扫描范围，确保构建时只生成使用到的样式类
//
// 颜色令牌由两条**互相独立**的轴决定，故 <html> 上是「class 管色相、data-mode 管明暗」：
//   色相轴 —— brand 三档 + 表面三色（surface 页面底 / card 卡片底 / panel 深面板），
//             由 tailwindcss-themer 接管：插件把每套主题的色值转成 CSS 变量（默认主题 :root、
//             命名主题同名 class 作用域），运行时挂 theme-jade 这类 class 即全局换色。
//             色板见 src/config/themePalette.js。
//   明暗轴 —— 中性文字（ink 三档）、浅底色（cloud / elevated / scrim / paper）、琥珀与语义色，
//             以及各色相的深色表面，全部定义在 assets/main.css 的
//             :root（浅色）与 html[data-mode="dark"]（深色）。
//
// 所有颜色统一走 var(--colors-*) 通道写法：triplet + <alpha-value>，
// 因此 bg-brand/10、border-ink/5 这类透明度写法不受影响。
import themer from 'tailwindcss-themer'
import { THEME_PALETTE } from './src/config/themePalette.js'

const v = (name) => `rgb(var(--colors-${name}) / <alpha-value>)`

const themeShades = (t) => ({
  brand: { DEFAULT: t.brand, light: t.light, dark: t.dark },
  // 文字专用档：浅色取 brandInk（仅原值不达标的主题才偏离 brand），深色由 main.css 覆盖成亮色档
  'brand-ink': { DEFAULT: t.brandInk, strong: t.brandInkStrong },
  surface: t.surface,
  card: t.card,
  panel: t.panel,
})
const [defaultPalette, ...otherPalettes] = THEME_PALETTE

export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: v('ink'),
          soft: v('ink-soft'),
          muted: v('ink-muted')
        },
        paper: v('paper'),
        cloud: v('cloud'),
        // 浮层 / 输入框底：比 card 再高一档，维持「panel < surface < cloud < card < elevated」层次
        elevated: v('elevated'),
        // 遮罩专用：明暗两态都保持偏暗（叠加式遮罩在深色下不能翻成浅色）
        scrim: v('scrim'),
        amber: {
          DEFAULT: v('amber'),
          soft: v('amber-soft')
        },
        success: { DEFAULT: v('success'), soft: v('success-soft') },
        warning: { DEFAULT: v('warning'), soft: v('warning-soft') },
        danger: { DEFAULT: v('danger'), soft: v('danger-soft') },
        info: { DEFAULT: v('info'), soft: v('info-soft') }
      },
      // ⚠️**每个色相的文字用色都必须与填充用色分开**：填充要压得住白字（得偏暗），
      // 文字要压在浅底（得够深）与深底（得够亮）上都达标，一个色值不可能同时满足。
      // 这不是 brand 一家的特例：语义色同样一路两用——text-success 画在白底上只有
      // 3.30、text-amber 画在自带 /10 淡底上只有 1.89，而 bg-success / bg-amber 又要够饱和。
      // textColor 独立于 colors 配置，于是 text-* 与 bg-* 指向不同变量，
      // 全站调用点一个字都不用改，也不需要任何 dark: 前缀。
      textColor: {
        brand: {
          DEFAULT: v('brand-ink'),
          dark: v('brand-ink-strong'),
          light: v('brand-light')
        },
        // 语义色的文字档定义在 main.css（浅色深色各一组，见 :root 与 html[data-mode="dark"]）
        amber: v('amber-ink'),
        success: v('success-ink'),
        warning: v('warning-ink'),
        danger: v('danger-ink'),
        info: v('info-ink')
      }
    }
  },
  plugins: [
    themer({
      defaultTheme: {
        extend: {
          colors: themeShades(defaultPalette)
        }
      },
      themes: otherPalettes.map((t) => ({
        name: t.cls,
        extend: {
          colors: themeShades(t)
        }
      }))
    })
  ]
}
