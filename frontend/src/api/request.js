// axios 实例封装：统一 baseURL、超时、请求/响应拦截、并发取消
// [错误提示约定] 失败默认由本模块统一 toast（store/视图无需各自 catch+toast）；
// 调用方若自行处理错误（如批量操作逐条汇总、表单内联提示），在请求配置传
// { silent: true } 关闭全局提示，避免双重 toast。
import axios from 'axios'
import { bus, EVENTS } from '@/utils/eventBus'
import { toast } from '@/utils/toast'

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
    // blob 响应（图片流）不经 {code,message,data} 解包，原样放行
    if (response.config.responseType === 'blob') return response.data
    const res = response.data
    // 约定后端成功时 code === 0
    if (res.code !== 0 && res.code !== undefined) {
      const message = res.message || '请求失败'
      if (!response.config.silent) toast(message, 'error')
      return Promise.reject(new Error(message))
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
    if (res && res.message) {
      message = res.message
    } else if (!error.response) {
      // 无响应 = 断网/超时/DNS 失败：axios 原文是英文技术信息（"Network Error"、
      // "timeout of 10000ms exceeded"），对用户无意义，统一转成可行动的中文提示
      message = '网络连接异常，请检查网络后重试'
    } else if (error.message) {
      message = error.message
    }

    // Token 过期/非法（非登录接口）：走 auth store 的清理链并跳回登录页。
    // 此前只清 localStorage——不 emit AUTH_LOGOUT（并发请求取消、blob 缓存释放链失效）、
    // 不清 Pinia token（守卫仍放行死 token）。动态 import 避免
    // 与 stores/auth.js 的静态循环依赖（auth → api/auth → 本模块）。
    // [权限判断] 前端清理只是体验优化，真正的拦截由后端鉴权装饰器保证
    if (status === 401 && !url.includes('/auth/login')) {
      import('@/stores/auth').then(({ useAuthStore }) => {
        useAuthStore().clearSession()
        bus.emit(EVENTS.AUTH_LOGOUT)
      })
      if (location.pathname !== '/login') location.href = '/login'
    } else if (!error.config?.silent) {
      // 统一错误提示（401 已由跳转登录页兜底，不再叠加 toast）
      toast(message, 'error')
    }
    error.message = message
    return Promise.reject(error)
  }
)

// 订阅登出事件：退出登录时由事件总线统一通知此处取消并发请求，
// 取代 auth store 直接 import 本模块的耦合，使 auth 与请求层互不硬连线。
bus.on(EVENTS.AUTH_LOGOUT, () => cancelPendingRequests())

export default service
