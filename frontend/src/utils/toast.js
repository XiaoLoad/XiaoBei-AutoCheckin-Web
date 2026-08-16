// 全局轻提示（Toast）：单例响应式状态 + 触发函数，供路由守卫等非组件上下文调用
import { reactive } from 'vue'

export const toastState = reactive({
  show: false,
  message: '',
  // 'info' | 'success' | 'error' | 'warning'
  type: 'info'
})

let timer = null

// 弹出一条提示；同一时刻只显示最新一条，自动消失
export function toast(message, type = 'info', duration = 2600) {
  toastState.message = message
  toastState.type = type
  toastState.show = true
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => {
    toastState.show = false
  }, duration)
}

export default toast
