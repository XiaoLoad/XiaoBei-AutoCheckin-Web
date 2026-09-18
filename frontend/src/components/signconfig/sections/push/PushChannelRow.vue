<template>
  <!-- 逐通道落位行：左侧通道徽标 + 状态徽标，体内控件由调用方按凭证来源填。
       三种来源下几何不变，扫一列状态徽标就知道哪个通道送不到。 -->
  <div class="flex items-start gap-2.5 py-2.5">
    <span class="grid h-6 w-6 shrink-0 place-items-center rounded-md text-[10px] font-bold" :class="channelTone(channel)">
      {{ channelShort(channel) }}
    </span>
    <div class="min-w-0 flex-1 space-y-1.5">
      <div class="flex items-center gap-2">
        <span class="text-xs text-ink-soft">{{ channelLabel(channel) }}</span>
        <span class="inline-flex shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium" :class="tone.cls">
          <span class="h-1 w-1 rounded-full" :class="tone.dot" />
          {{ state.text || '—' }}
        </span>
      </div>
      <p v-if="state.detail" class="text-[11px] text-ink-muted">{{ state.detail }}</p>
      <slot />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { channelLabel, channelShort, channelTone } from '@/utils/pushChannels'

const props = defineProps({
  channel: { type: String, required: true },
  // 核对结论：{ state: ok|warn|gap|idle, text, detail }
  state: { type: Object, default: () => ({}) }
})

const TONES = {
  ok: { cls: 'bg-success/10 text-success-ink', dot: 'bg-success' },
  warn: { cls: 'bg-warning/10 text-warning-ink', dot: 'bg-warning' },
  gap: { cls: 'bg-danger/10 text-danger-ink', dot: 'bg-danger' },
  idle: { cls: 'bg-ink/5 text-ink-muted', dot: 'bg-ink/30' }
}
const tone = computed(() => TONES[props.state.state] || TONES.idle)
</script>
