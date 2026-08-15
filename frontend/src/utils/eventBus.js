// 轻量事件总线（mitt 风格的极简实现，零额外依赖）
// 用于解耦跨模块副作用，避免模块间硬连线——例如退出登录时统一通知请求层取消并发请求，
// 取代 auth store 直接依赖 api/request 的反向耦合。
const listeners = new Map()

export const bus = {
  on(type, fn) {
    if (!listeners.has(type)) listeners.set(type, new Set())
    listeners.get(type).add(fn)
    return () => bus.off(type, fn)
  },
  off(type, fn) {
    listeners.get(type)?.delete(fn)
  },
  emit(type, payload) {
    listeners.get(type)?.forEach((fn) => fn(payload))
  },
  clear() {
    listeners.clear()
  }
}

// 事件名常量，避免拼写漂移
export const EVENTS = {
  AUTH_LOGOUT: 'auth:logout'
}
