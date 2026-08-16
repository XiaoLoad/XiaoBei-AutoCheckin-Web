<template>
  <!-- 全局 Toast 宿主：挂载到 body，独立于任何布局，保证守卫等任意位置都能触发 -->
  <Teleport to="body">
    <div class="fixed left-1/2 top-6 z-[100] -translate-x-1/2 pointer-events-none">
      <Transition name="toast">
        <div
          v-if="toastState.show"
          class="flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium shadow-lg ring-1 backdrop-blur"
          :class="toneClass"
          role="alert"
        >
          <Icon :name="iconName" :size="16" />
          <span>{{ toastState.message }}</span>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { toastState } from '@/utils/toast'
import Icon from '@/components/Icon.vue'

const toneClass = computed(() => {
  switch (toastState.type) {
    case 'error':
      return 'bg-danger/10 text-danger ring-danger/20'
    case 'success':
      return 'bg-success/10 text-success ring-success/20'
    case 'warning':
      return 'bg-amber/10 text-amber ring-amber/20'
    default:
      return 'bg-ink/10 text-ink ring-ink/15'
  }
})

const iconName = computed(() => {
  switch (toastState.type) {
    case 'success':
      return 'check'
    default:
      // 'alert' 同时覆盖 error / warning / info 的语义
      return 'alert'
  }
})
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
