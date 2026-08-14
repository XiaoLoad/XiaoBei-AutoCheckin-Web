/** @type {import('tailwindcss').Config} */
// TailwindCSS 配置文件
// content 指定扫描范围，确保构建时只生成使用到的样式类
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#1674f8',
          light: '#4a9aff',
          dark: '#0f5dd4',
          50: '#e8f2ff',
          100: '#d1e5ff',
          200: '#a3cbff',
          300: '#75b1ff',
          400: '#4a9aff',
          500: '#1674f8',
          600: '#0f5dd4',
          700: '#0b47b0',
          800: '#08358c',
          900: '#052669'
        },
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
        cloud: '#EEF2F9'
      }
    }
  },
  plugins: []
}
