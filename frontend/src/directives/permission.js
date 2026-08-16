// 按钮级权限指令 v-permission：无权限时直接从 DOM 移除元素（而非仅隐藏），
// 避免残留可点击/可聚焦的危险操作（如普通用户看到「删除用户」按钮）。
// 用法：
//   v-permission="['admin']"     仅管理员可见
//   v-permission="'user'"        仅普通用户可见
//   v-permission="['admin','user']"  两者均可
//   不传值                         视为不限制（保持可见）
// 思路参考 vue-element-admin 的 permission 指令，但鉴权决策收敛到 auth store 的 role。
import { useAuthStore } from '@/store/modules/auth'

// 单一决策：当前角色是否满足指令要求的角色集合
export function hasRole(role, value) {
  if (!value) return true
  const allowed = Array.isArray(value) ? value : [value]
  if (role === 'admin') return true // 管理员拥有全部权限
  return allowed.includes(role)
}

export default {
  mounted(el, binding) {
    const auth = useAuthStore()
    if (!hasRole(auth.role, binding.value)) {
      el.parentNode && el.parentNode.removeChild(el)
    }
  }
}
