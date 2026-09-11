// 顶部全局加载条状态（HTTP 层驱动）。
//
// 背景：进度条原先只由 refreshBus 驱动，而各 store 仅在「静默刷新」分支登记总线，
// 于是首屏加载、二级页面取数、以及未接入总线的 store（如全站签到记录）都不亮条。
// 现改为在 axios 层按请求计数——任何发出的请求都计入，天然覆盖首屏 / 翻页筛选 /
// 抽屉与模态框取数 / 二级页面，无需各 store 逐个接入。
//
// 两个常量是刻意的取舍：
//   SHOW_DELAY  抑制毫秒级请求的闪烁。快请求本来就看不清，为它强行亮 300ms 反而
//               拖慢感知；超过该时长仍未完成的请求才亮条。
//   MIN_VISIBLE 已亮起的条至少停留这么久，避免"刚出现就消失"的一闪。
//
// 后台轮询类请求（如「正在进行」卡片每 2 分钟静默刷新）在请求配置里传
// skipLoadingBar: true 主动豁免，避免长期噪音。
import { ref, computed } from 'vue'

const SHOW_DELAY = 50
const MIN_VISIBLE = 300

// 在途请求数
const pending = ref(0)
// 条的可见性（带延迟与最短展示时间，避免闪烁）
const shown = ref(false)
let showTimer = null
let hideTimer = null
let shownAt = 0

export const httpPending = computed(() => pending.value)
export const loadingBarShown = computed(() => shown.value)

function scheduleShow() {
  if (shown.value || showTimer) return
  showTimer = setTimeout(() => {
    showTimer = null
    shown.value = true
    shownAt = Date.now()
  }, SHOW_DELAY)
}

function scheduleHide() {
  if (pending.value > 0) return
  // 还没亮起来就结束了：取消待执行的显示，直接不亮（快请求不留痕迹）
  if (showTimer) {
    clearTimeout(showTimer)
    showTimer = null
    return
  }
  if (!shown.value) return
  const rest = Math.max(0, MIN_VISIBLE - (Date.now() - shownAt))
  if (hideTimer) clearTimeout(hideTimer)
  hideTimer = setTimeout(() => {
    hideTimer = null
    if (pending.value === 0) shown.value = false
  }, rest)
}

export function beginLoad() {
  pending.value += 1
  // 收尾计时器作废：又来了新请求，继续亮着
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
  scheduleShow()
}

export function endLoad() {
  pending.value = Math.max(0, pending.value - 1)
  scheduleHide()
}

// 退出登录等场景下中止并发请求时兜底清零，防止计数泄漏导致进度条永不熄灭
export function resetLoads() {
  if (showTimer) {
    clearTimeout(showTimer)
    showTimer = null
  }
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
  pending.value = 0
  shown.value = false
}
