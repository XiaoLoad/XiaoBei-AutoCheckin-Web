// 应用入口：挂载 Vue 实例、路由、状态管理、全局样式
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import pinia from './store'
import './assets/main.css'

const app = createApp(App)

app.use(router)
app.use(pinia)

app.mount('#app')
