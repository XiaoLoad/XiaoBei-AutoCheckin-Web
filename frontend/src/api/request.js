// axios 实例封装：统一 baseURL、超时、请求/响应拦截、并发取消
import axios from 'axios'
import { bus, EVENTS } from '@/utils/eventBus'

const service = axios.create({
  // 开发环境通过 Vite 代理转发到后端（见 vite.config.js）
  baseURL: '/api',
  timeout: 10000
})

// 待处理请求控制器集合：退出登录时用于中止仍在进行的并发请求，
// 避免它们在 token 失效后拿到 401 误触发跳转 / 报错。
const pendingControllers = new Set()

function trackRequest(config) {
  const controller = new AbortController()
  config.signal = controller.signal
  config.__controller = controller
  pendingControllers.add(controller)
}

function untrackRequest(config) {
  if (config && config.__controller) {
    pendingControllers.delete(config.__controller)
  }
}

// 退出登录时调用：中止所有尚未完成的请求
export function cancelPendingRequests() {
  pendingControllers.forEach((c) => c.abort('logout'))
  pendingControllers.clear()
}

// 请求拦截：统一附加 Bearer token
service.interceptors.request.use(
  (config) => {
    trackRequest(config)
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    untrackRequest(error.config)
    return Promise.reject(error)
  }
)

// 响应拦截：解包后端 { code, message, data }，统一处理 401/403
service.interceptors.response.use(
  (response) => {
    untrackRequest(response.config)
    const res = response.data
    // 约定后端成功时 code === 0
    if (res.code !== 0 && res.code !== undefined) {
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    return res.data
  },
  (error) => {
    untrackRequest(error.config)

    // 主动取消的请求（如退出登录时中止的并发请求）直接抛出，不做任何处理
    if (axios.isCancel(error)) {
      return Promise.reject(error)
    }

    const res = error.response?.data
    const status = error.response?.status
    const url = error.config?.url || ''
    let message = '请求失败'
    if (res && res.message) message = res.message
    else if (error.message) message = error.message

    // Token 过期/非法（非登录接口）：清除本地登录态并跳回登录页
    // [权限判断] 前端清理只是体验优化，真正的拦截由后端鉴权装饰器保证
    if (status === 401 && !url.includes('/auth/login')) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (location.pathname !== '/login') location.href = '/login'
    }
    error.message = message
    return Promise.reject(error)
  }
)

// 订阅登出事件：退出登录时由事件总线统一通知此处取消并发请求，
// 取代 auth store 直接 import 本模块的耦合，使 auth 与请求层互不硬连线。
bus.on(EVENTS.AUTH_LOGOUT, () => cancelPendingRequests())

export default service
