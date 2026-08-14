// 鉴权状态（Pinia）：持有 token / 用户信息 / 角色，并持久化到 localStorage
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authApi from '@/api/auth'
import { cancelPendingRequests } from '@/api/request'

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
      // 3) 取消仍在进行的并发请求，避免它们拿到 401 后误触发跳转 / 报错
      cancelPendingRequests()
      loggingOut.value = false
    }
  }

  return {
    token,
    user,
    isAuthenticated,
    role,
    isAdmin,
    username,
    login,
    logout,
    loggingOut,
  }
})

function parseUser(raw) {
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}
