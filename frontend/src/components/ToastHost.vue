<template>
  <!-- 全局 Toast 宿主：挂载到 body，独立于任何布局，保证守卫等任意位置都能触发。
       队列渲染（utils/toast.js）：同屏最多 3 条、各自计时，连发不再互相覆盖。
       样式与全站卡片语言同源：实心主题卡（bg-card 随主题）+ 环形图标章承载语义色，
       文字恒为 ink 保证可读；语义色只落在图标章上，不再使用半透明色调底。 -->
  <Teleport to="body">
    <div class="pointer-events-none fixed left-1/2 top-6 z-[100] flex -translate-x-1/2 flex-col items-center gap-2">
      <TransitionGroup name="toast">
        <div
          v-for="t in toastState.list"
          :key="t.id"
          class="flex items-center gap-3 rounded-2xl bg-card py-2.5 pl-2.5 pr-5 shadow-[0_1px_2px_rgba(20,33,61,0.06),0_18px_40px_-18px_rgba(20,33,61,0.4)] ring-1 ring-ink/5"
          role="alert"
        >
          <span class="grid h-8 w-8 shrink-0 place-items-center rounded-full" :class="iconWrapCls(t.type)" aria-hidden="true">
            <Icon :name="iconName(t.type)" :size="16" />
          </span>
          <span class="text-sm font-medium text-ink">{{ t.message }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { toastState } from '@/utils/toast'
import Icon from '@/components/Icon.vue'

// 语义色只落在图标章：成功绿 / 错误红 / 警告琥珀 / 信息品牌蓝
function iconWrapCls(type) {
  switch (type) {
    case 'error':
      return 'bg-danger/10 text-danger'
    case 'success':
      return 'bg-success/10 text-success'
    case 'warning':
      return 'bg-warning/10 text-warning'
    default:
      return 'bg-brand/10 text-brand'
  }
}

function iconName(type) {
  switch (type) {
    case 'success':
      return 'check-circle'
    case 'error':
      return 'x-circle'
    case 'warning':
      return 'alert'
    default:
      return 'info'
  }
}
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(-10px) scale(0.97);
}
/* 离场项脱离文档流，其余 toast 平滑补位 */
.toast-leave-active {
  position: absolute;
}
.toast-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
.toast-move {
  transition: transform 0.25s ease;
}
</style>
