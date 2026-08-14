// 应用入口：挂载 Vue 实例、路由、状态管理、全局样式
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import pinia from './store'
import './assets/main.css'

const app = createApp(App)

// 必须先把 Pinia 装好，路由守卫中才能使用 auth store
app.use(pinia)
app.use(router)

app.mount('#app')
