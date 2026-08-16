// 应用入口：挂载 Vue 实例、路由、状态管理、全局样式
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import pinia from './store'
import permission from '@/directives/permission'
import './assets/main.css'

const app = createApp(App)

// 必须先把 Pinia 装好，路由守卫中才能使用 auth store
app.use(pinia)
app.use(router)

// 注册按钮级权限指令 v-permission（无权限时移除元素）
app.directive('permission', permission)

app.mount('#app')
