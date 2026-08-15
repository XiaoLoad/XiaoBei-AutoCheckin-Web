<template>
  <section class="rounded-xl border border-ink/10 bg-white/60 p-4">
    <header class="mb-3 flex items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <span class="grid place-items-center h-7 w-7 rounded-lg bg-brand/10 text-brand">
          <Icon :name="icon" :size="16" />
        </span>
        <h4 class="text-sm font-semibold text-ink">{{ title }}</h4>
      </div>
      <span v-if="source" class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium" :class="sourceCls">
        <span class="h-1.5 w-1.5 rounded-full" :class="sourceDot" />
        {{ sourceLabel }}
      </span>
    </header>
    <slot />
  </section>
</template>

<script setup>
import { computed } from 'vue'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  title: { type: String, required: true },
  icon: { type: String, default: 'sliders' },
  // 来源徽标：'system' 系统默认 / 'user' 用户默认 / 'overridden' 已覆盖（任务实例单独改过）
  source: { type: String, default: '' }
})

const meta = {
  system: { label: '系统默认', cls: 'bg-ink/10 text-ink-muted', dot: 'bg-ink-muted' },
  user: { label: '用户默认', cls: 'bg-info/10 text-info', dot: 'bg-info' },
  overridden: { label: '已覆盖', cls: 'bg-amber/15 text-amber', dot: 'bg-amber' }
}
const sourceLabel = computed(() => (meta[props.source] || {}).label || '')
const sourceCls = computed(() => (meta[props.source] || {}).cls || '')
const sourceDot = computed(() => (meta[props.source] || {}).dot || '')
</script>
