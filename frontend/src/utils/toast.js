// 全局轻提示（Toast）：队列化响应式状态 + 触发函数，供路由守卫等非组件上下文调用。
// 队列化（此前为单例覆盖式）：同一操作连发的多条提示（如批量启用「成功 N 条 + 跳过 M 条」
// 同帧触发）此前会互相覆盖、成功反馈必然丢失；现按条入队、各自计时自动消失，
// 同屏上限 3 条、超出 FIFO 淘汰最旧的。
import { reactive } from 'vue'

export const toastState = reactive({
  // [{ id, message, type }]，type: 'info' | 'success' | 'error' | 'warning'
  list: []
})

const DURATION_DEFAULT = 2600
const MAX_VISIBLE = 3

let uid = 0
const timers = new Map()

function dismiss(id) {
  const idx = toastState.list.findIndex((t) => t.id === id)
  if (idx !== -1) toastState.list.splice(idx, 1)
  const timer = timers.get(id)
  if (timer) {
    clearTimeout(timer)
    timers.delete(id)
  }
}

// 弹出一条提示；同一时刻最多同屏 MAX_VISIBLE 条，各自独立计时
export function toast(message, type = 'info', duration = DURATION_DEFAULT) {
  const item = { id: ++uid, message, type }
  toastState.list.push(item)
  while (toastState.list.length > MAX_VISIBLE) {
    dismiss(toastState.list[0].id)
  }
  timers.set(item.id, setTimeout(() => dismiss(item.id), duration))
}

export default toast
