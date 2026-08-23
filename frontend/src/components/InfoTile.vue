<template>
  <div class="rounded-xl border border-ink/10 bg-white/60 p-3.5">
    <div class="flex items-center gap-1.5 text-xs text-ink-muted">
      <Icon v-if="icon" :name="icon" :size="13" />
      <span>{{ label }}</span>
    </div>
    <div class="mt-1.5 text-sm font-medium text-ink">
      <!-- 具名插槽优先：用于放徽标等自定义内容；否则展示 value 文本 -->
      <slot>{{ value }}</slot>
    </div>
  </div>
</template>

<script setup>
import Icon from '@/components/Icon.vue'

defineProps({
  label: { type: String, required: true },
  value: { type: String, default: '' },
  icon: { type: String, default: '' }
})
</script>
