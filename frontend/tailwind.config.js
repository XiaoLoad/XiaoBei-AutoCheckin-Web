/** @type {import('tailwindcss').Config} */
// TailwindCSS 配置文件
// content 指定扫描范围，确保构建时只生成使用到的样式类
//
// 主题色托管：brand 三档 + 表面三色（surface 页面底 / card 卡片底 / panel 深面板）
// 由 tailwindcss-themer 接管——插件把每套主题的色值转成 CSS 变量（默认主题 :root、
// 命名主题同名 class 作用域），运行时给 <html> 挂主题 class（如 theme-jade）即全局换色，
// bg-brand/10、bg-card/80 等透明度写法自动兼容。色板定义见 src/config/themePalette.js。
// 其余颜色（ink 文字/paper/语义色等）不随主题切换，保持静态定义。
import themer from 'tailwindcss-themer'
import { THEME_PALETTE } from './src/config/themePalette.js'

const themeShades = (t) => ({
  brand: { DEFAULT: t.brand, light: t.light, dark: t.dark },
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
          DEFAULT: '#14213D',
          soft: '#27324F',
          muted: '#5B6478'
        },
        paper: '#FBF7F0',
        amber: {
          DEFAULT: '#F2A65A',
          soft: '#F8C58A'
        },
        cloud: '#EEF2F9',
        success: { DEFAULT: '#16a34a', soft: '#dcfce7' },
        warning: { DEFAULT: '#d97706', soft: '#fef3c7' },
        danger: { DEFAULT: '#dc2626', soft: '#fee2e2' },
        info: { DEFAULT: '#0ea5e9', soft: '#e0f2fe' }
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
