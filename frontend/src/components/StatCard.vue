<template>
  <div class="dash-card p-5 flex flex-col gap-3 fade-up" :class="`delay-${delay}`">
    <div class="flex items-start justify-between">
      <span class="text-sm font-medium text-ink-muted">{{ label }}</span>
      <span class="grid place-items-center w-9 h-9 rounded-xl" :class="iconWrapClass">
        <Icon :name="icon" :size="18" />
      </span>
    </div>
    <div class="flex items-end gap-1.5">
      <span class="text-3xl font-bold text-ink tabular-nums leading-none">{{ value }}</span>
      <span v-if="unit" class="text-sm text-ink-muted mb-0.5">{{ unit }}</span>
    </div>
    <div v-if="delta !== null" class="flex items-center gap-1 text-xs" :class="deltaClass">
      <Icon :name="deltaIcon" :size="14" />
      <span class="font-medium">{{ delta }}</span>
      <span class="text-ink-muted/70">· {{ deltaHint }}</span>
    </div>
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
  delay: { type: Number, default: 1 }
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
