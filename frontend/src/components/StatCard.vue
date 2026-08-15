<template>
  <div
    class="dash-card flex flex-col fade-up"
    :class="[
      compact ? 'min-h-[72px] gap-2 p-3' : 'min-h-[120px] gap-3 p-5',
      `delay-${delay}`
    ]"
  >
    <!-- 骨架占位：数据加载期间展示，宽度/高度与真实内容一致，避免卡片高度抖动 -->
    <template v-if="loading">
      <div class="flex items-start justify-between">
        <div class="h-4 w-20 rounded bg-ink/5 animate-pulse" />
        <div class="h-9 w-9 rounded-xl bg-ink/5 animate-pulse" :class="compact ? 'h-8 w-8 sm:h-9 sm:w-9' : 'h-9 w-9'" />
      </div>
      <div class="h-8 w-16 rounded bg-ink/5 animate-pulse" />
      <div v-if="delta !== null" class="h-3 w-28 rounded bg-ink/5 animate-pulse" />
    </template>
    <template v-else>
      <div class="flex items-start justify-between">
        <span class="font-medium text-ink-muted" :class="compact ? 'text-xs' : 'text-sm'">{{ label }}</span>
        <span class="grid place-items-center rounded-xl" :class="[iconWrapClass, compact ? 'h-8 w-8 sm:h-9 sm:w-9' : 'h-9 w-9']">
          <Icon :name="icon" :size="18" :class="compact ? 'sm:h-5 sm:w-5' : ''" />
        </span>
      </div>
      <div class="flex items-end gap-1.5">
        <span class="font-bold text-ink tabular-nums leading-none" :class="compact ? 'text-2xl' : 'text-3xl'">{{ value }}</span>
        <span v-if="unit" class="text-ink-muted" :class="compact ? 'text-xs mb-0.5' : 'text-sm mb-0.5'">{{ unit }}</span>
      </div>
      <div v-if="delta !== null" class="flex items-center gap-1 text-xs" :class="deltaClass">
        <Icon :name="deltaIcon" :size="12" />
        <span class="font-medium">{{ delta }}</span>
        <span class="text-ink-muted/70">· {{ deltaHint }}</span>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  unit: { type: String, default: '' },
  icon: { type: String, default: 'check' },
  tone: { type: String, default: 'brand' }, // brand | amber | success | danger | info
  delta: { type: [String, Number], default: null },
  deltaType: { type: String, default: 'flat' }, // up | down | flat
  deltaHint: { type: String, default: '较昨日' },
  delay: { type: Number, default: 1 },
  // 紧凑模式：用于移动端或高密度页面，减小内边距与字号
  compact: { type: Boolean, default: false },
  // 加载态：true 时渲染骨架占位，配合父级在数据返回前传入避免卡片跳动
  loading: { type: Boolean, default: false }
})

const toneMap = {
  brand: 'bg-brand/10 text-brand',
  amber: 'bg-amber/15 text-amber',
  success: 'bg-success/10 text-success',
  danger: 'bg-danger/10 text-danger',
  info: 'bg-info/10 text-info'
}
const iconWrapClass = computed(() => toneMap[props.tone] || toneMap.brand)

const deltaClass = computed(() => {
  if (props.deltaType === 'up') return 'text-success'
  if (props.deltaType === 'down') return 'text-danger'
  return 'text-ink-muted'
})
const deltaIcon = computed(() =>
  props.deltaType === 'up' ? 'arrowUp' : props.deltaType === 'down' ? 'arrowDown' : 'clock'
)
</script>
