// 鉴权状态（Pinia）：持有 token / 用户信息 / 角色，并持久化到 localStorage
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authApi from '@/api/auth'
import { bus, EVENTS } from '@/utils/eventBus'

const TOKEN_KEY = 'token'
const USER_KEY = 'user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref(parseUser(localStorage.getItem(USER_KEY)))

  // 退出中标记：防止并发点击 / 重复触发导致重复请求或竞态
  const loggingOut = ref(false)

  const isAuthenticated = computed(() => !!token.value)
  const role = computed(() => user.value?.role || '')
  const isAdmin = computed(() => role.value === 'admin')
  const username = computed(() => user.value?.username || '')

  // 校验当前 token 是否仍有效：除本地存在外，还需未过期（比对 JWT 的 exp 声明）。
  // 仅判断 isAuthenticated 不足以拦截过期 token —— 否则会先渲染受保护页面，
  // 再由接口 401 兜底跳转，造成"先闪框架再跳登录"的体验问题。
  function isSessionValid() {
    const raw = token.value
    if (!raw) return false
    try {
      const payload = decodeJwt(raw)
      if (!payload) return false
      if (payload.exp && payload.exp * 1000 <= Date.now()) return false
      return true
    } catch {
      return false
    }
  }

  // 统一的可访问性决策：是否允许进入某路由。
  // 把「是否登录 + 会话是否有效 + 角色是否匹配」收敛为单一入口，
  // 路由守卫不再散点读取内部状态，降低守卫与 store 内部结构的耦合。
  function canAccess(route) {
    const meta = route.meta || {}
    if (!meta.requiresAuth) return true
    if (!(isAuthenticated.value && isSessionValid())) return false
    const roles = meta.roles
    if (roles && roles.length && !roles.includes(role.value)) return false
    return true
  }

  function persist() {
    if (token.value) localStorage.setItem(TOKEN_KEY, token.value)
    else localStorage.removeItem(TOKEN_KEY)
    if (user.value) localStorage.setItem(USER_KEY, JSON.stringify(user.value))
    else localStorage.removeItem(USER_KEY)
  }

  function setSession(tokenValue, userValue) {
    token.value = tokenValue
    user.value = userValue
    persist()
  }

  // 调用登录接口并写入会话
  async function login(credentials) {
    const res = await authApi.login(credentials) // 响应拦截已解包为 data
    setSession(res.token, {
      user_id: res.user_id,
      username: res.username,
      role: res.role,
    })
    return res
  }

  // 清理本地会话：清空内存态与持久化凭证，重置为未登录
  function _clearSession() {
    token.value = ''
    user.value = null
    persist()
  }

  // 仅清理本地会话（不发起网络请求），供路由守卫在发现无效 token 时直接拦截重定向
  function clearSession() {
    _clearSession()
  }

  // 退出登录：服务端吊销 token + 客户端清理 + 并发/异常兜底
  async function logout() {
    if (loggingOut.value) return
    loggingOut.value = true
    try {
      // 1) 通知服务端将当前 token 加入黑名单，使其立即失效。
      //    即便请求失败（网络/服务异常），也必须保证本地退出 → catch 兜底。
      await authApi.logout().catch(() => {})
    } finally {
      // 2) 无论如何都清除本地会话与凭证
      _clearSession()
      // 3) 发布登出事件，由事件总线统一通知关注方（如请求层取消并发请求），
      //    取代 auth store 直接依赖 api/request 的反向耦合。
      bus.emit(EVENTS.AUTH_LOGOUT)
      loggingOut.value = false
    }
  }

  return {
    token,
    user,
    isAuthenticated,
    isSessionValid,
    canAccess,
    role,
    isAdmin,
    username,
    login,
    logout,
    clearSession,
    loggingOut,
  }
})

// 仅做本地解码读取 payload（用于校验 exp），不做签名验证（签名由后端负责）。
// 解析失败返回 null，交由调用方按"无效"处理。
function decodeJwt(raw) {
  try {
    const seg = raw.split('.')[1]
    if (!seg) return null
    const b64 = seg.replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(
      atob(b64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(json)
  } catch {
    return null
  }
}

function parseUser(raw) {
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}
