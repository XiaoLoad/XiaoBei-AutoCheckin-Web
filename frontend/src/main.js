// 应用入口：挂载 Vue 实例、路由、状态管理、全局样式
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router, { syncInitialRoutes } from './router'
import permission from '@/directives/permission'
import reveal from '@/directives/reveal'
import './assets/main.css'
// PhotoSwipe 灯箱样式全局加载：组件级按需注入在 dev/HMR 下偶发不生效（灯箱无样式、图片拉伸铺满）
import 'photoswipe/dist/photoswipe.css'

const app = createApp(App)

// 必须先把 Pinia 装好，路由守卫 / 初始路由同步中才能使用 auth store
app.use(createPinia())
app.use(router)

// 刷新场景下，按本地持久化的会话预注册动态路由，使当前页可直接解析（不再跳仪表盘）
syncInitialRoutes()

// 注册按钮级权限指令 v-permission（无权限时移除元素）
app.directive('permission', permission)
// 注册滚动渐入指令 v-reveal（元素进入视口时 GSAP 淡入上移）
app.directive('reveal', reveal)

app.mount('#app')
