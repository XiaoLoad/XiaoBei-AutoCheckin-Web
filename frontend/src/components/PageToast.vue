<template>
  <!-- 页面级轻提示：右下角深色底，操作反馈统一出口（样式基准取自用户管理页）。
       与全局 ToastHost（顶部居中、语义色调）分工：本组件只做页面动作结果的就近反馈 -->
  <Teleport to="body">
    <Transition name="page-toast">
      <div
        v-if="show"
        class="fixed bottom-6 right-6 z-[1100] flex items-center gap-2 rounded-xl bg-ink px-3 py-2.5 align-middle text-sm font-medium text-white shadow-2xl"
        role="alert"
      >
        <Icon :name="type === 'error' ? 'alert' : 'check'" :size="16" :class="type === 'error' ? 'text-danger' : 'text-success'" />
        {{ message }}
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import Icon from '@/components/Icon.vue'

// 受控组件：状态由调用方持有（reactive + 定时器），保证触发时机与文案完全由页面决定
defineProps({
  show: { type: Boolean, default: false },
  message: { type: String, default: '' },
  // 'success' | 'error'（其余值按 success 处理）
  type: { type: String, default: 'success' }
})
</script>

<style scoped>
/* 入场自下而上浮入，与全局 Toast 的下沉方向呼应其顶部位置 */
.page-toast-enter-active,
.page-toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.page-toast-enter-from,
.page-toast-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
