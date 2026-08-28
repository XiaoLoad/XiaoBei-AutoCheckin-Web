<template>
  <div class="flex flex-1 min-h-0 flex-col gap-6">
    <!-- 任务日志占位页：功能尚未实现，仅展示入口与说明 -->
    <div class="dash-card fade-up flex flex-1 flex-col items-center justify-center gap-4 text-ink-muted">
      <Icon name="records" :size="44" class="opacity-40" />
      <div class="text-center">
        <p class="text-base font-medium text-ink-soft">任务日志</p>
        <p class="mt-1.5 text-sm">页面建设中，暂未实现。</p>
        <p class="mt-1 text-xs text-ink-muted/70">后续将展示各定时任务的执行记录与运行状态。</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import Icon from '@/components/Icon.vue'
</script>
