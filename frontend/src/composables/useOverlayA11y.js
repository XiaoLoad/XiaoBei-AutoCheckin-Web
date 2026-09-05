// 抽屉/弹窗类浮层的无障碍基线。此前仅 BaseModal 具备 ESC 关闭与滚动锁定，
// 四个抽屉（批量管理/批量应用/套用明细/任务设置）键盘用户无法 ESC 关闭、
// Tab 会穿透遮罩落到被覆盖的背景页。本组合式补齐三件事：
// - ESC 关闭：window keydown 监听，Escape 触发调用方的 requestClose（走关闭动画）
// - 初始焦点：挂载后聚焦面板（自动补 tabindex="-1"），键盘与读屏用户有明确入口
// - 背景滚动锁定：计数式 body overflow 锁，浮层叠加（抽屉内再开确认弹窗）时
//   只有全部浮层关闭才恢复滚动
// 用法：useOverlayA11y(panel, requestClose)；组件即浮层生命周期（v-if 挂载/卸载）。
import { onMounted, onBeforeUnmount, nextTick } from 'vue'

let lockCount = 0
let prevOverflow = ''

function acquireScrollLock() {
  if (lockCount === 0) {
    prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  }
  lockCount += 1
}

function releaseScrollLock() {
  lockCount = Math.max(0, lockCount - 1)
  if (lockCount === 0) {
    document.body.style.overflow = prevOverflow
  }
}

export function useOverlayA11y(panelRef, requestClose, { autoFocus = true, lockScroll = true } = {}) {
  let locked = false

  function onKeyDown(e) {
    if (e.key === 'Escape') requestClose()
  }

  onMounted(async () => {
    window.addEventListener('keydown', onKeyDown)
    if (lockScroll) {
      acquireScrollLock()
      locked = true
    }
    if (autoFocus) {
      await nextTick()
      const el = panelRef.value
      if (el) {
        if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1')
        el.focus({ preventScroll: true })
      }
    }
  })

  onBeforeUnmount(() => {
    window.removeEventListener('keydown', onKeyDown)
    if (locked) releaseScrollLock()
  })
}
