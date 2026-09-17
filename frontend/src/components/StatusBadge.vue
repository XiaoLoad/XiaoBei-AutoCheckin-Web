<template>
  <span
    class="inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
    :class="cls"
  >
    <span class="h-1.5 w-1.5 rounded-full" :class="dot" />
    {{ text }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

// 今日合并推送状态徽标：null=尚未推送；success=全部已签；partial=部分已签；fail=发送失败
const props = defineProps({
  today: { type: Object, default: null }
})

const meta = computed(() => {
  const t = props.today
  if (!t) return { text: '待推送', cls: 'bg-ink/5 text-ink-muted', dot: 'bg-ink/30' }
  if (t.status === 'success') return { text: '已推送', cls: 'bg-success/10 text-success', dot: 'bg-success' }
  if (t.status === 'partial') return { text: '部分已签', cls: 'bg-warning/10 text-warning', dot: 'bg-warning' }
  return { text: '发送失败', cls: 'bg-danger/10 text-danger', dot: 'bg-danger' }
})

const text = computed(() => {
  const t = props.today
  if (t && t.sentAt) return `${meta.value.text} · ${t.sentAt.slice(11)}`
  return meta.value.text
})
const cls = computed(() => meta.value.cls)
const dot = computed(() => meta.value.dot)
</script>
