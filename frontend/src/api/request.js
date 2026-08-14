// axios 实例封装：统一 baseURL、超时、请求/响应拦截
import axios from 'axios'

const service = axios.create({
  // 开发环境通过 Vite 代理转发到后端（见 vite.config.js）
  baseURL: '/api',
  timeout: 10000
})

// 请求拦截：可统一附加 token 等
service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截：统一解包后端 { code, message, data } 结构
service.interceptors.response.use(
  (response) => {
    const res = response.data
    // 约定后端成功时 code === 0
    if (res.code !== 0 && res.code !== undefined) {
      console.error('[API Error]', res.message)
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    return res.data
  },
  (error) => {
    console.error('[Request Error]', error)
    return Promise.reject(error)
  }
)

export default service
