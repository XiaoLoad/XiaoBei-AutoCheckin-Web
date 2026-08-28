<template>
  <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <!-- 总条数 / 当前页 -->
    <div class="flex items-center gap-2 text-sm text-ink-muted">
      <span>共 {{ total }} 条</span>
      <span class="hidden sm:inline">·</span>
      <span class="whitespace-nowrap">第 {{ page }} / {{ totalPages }} 页</span>
    </div>

    <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
      <!-- 每页条数 -->
      <div class="flex items-center gap-1.5 text-sm text-ink-muted">
        <span class="whitespace-nowrap">每页</span>
        <div class="w-28">
          <BaseSelect
            :model-value="pageSize"
            :options="sizeOptions"
            :searchable="false"
            :placement="'auto'"
            size="sm"
            @update:model-value="onSize"
          />
        </div>
        <span class="whitespace-nowrap">条</span>
      </div>

      <!-- 页码导航 -->
      <div class="inline-flex items-center rounded-xl bg-cloud p-1">
        <button
          type="button"
          class="grid h-8 w-8 place-items-center rounded-lg text-sm font-medium transition"
          :class="page <= 1 ? 'text-ink/30 cursor-not-allowed' : 'text-ink-muted hover:bg-white hover:text-ink'"
          :disabled="page <= 1"
          aria-label="上一页"
          @click="go(page - 1)"
        >
          <Icon name="chevron-left" :size="16" />
        </button>

        <template v-for="(p, i) in pages" :key="i">
          <span v-if="p === '...'" class="px-1.5 text-sm text-ink-muted select-none">…</span>
          <button
            v-else
            type="button"
            class="mx-0.5 inline-flex h-8 min-w-8 items-center justify-center rounded-lg px-2 text-sm font-medium transition"
            :class="p === page ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:bg-white hover:text-ink'"
            @click="go(p)"
          >
            {{ p }}
          </button>
        </template>

        <button
          type="button"
          class="grid h-8 w-8 place-items-center rounded-lg text-sm font-medium transition"
          :class="page >= totalPages ? 'text-ink/30 cursor-not-allowed' : 'text-ink-muted hover:bg-white hover:text-ink'"
          :disabled="page >= totalPages"
          aria-label="下一页"
          @click="go(page + 1)"
        >
          <Icon name="chevron-right" :size="16" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import BaseSelect from '@/components/BaseSelect.vue'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  page: { type: Number, required: true },
  pageSize: { type: Number, required: true },
  total: { type: Number, required: true },
  pageSizeOptions: { type: Array, default: () => [10, 20, 50] }
})

const emit = defineEmits(['update:page', 'update:pageSize'])

const sizeOptions = computed(() =>
  props.pageSizeOptions.map((n) => ({ value: n, label: String(n) }))
)

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

// 页码窗口：始终显示首/尾页，当前页前后各一页，过宽处用省略号替代
const pages = computed(() => {
  const tp = totalPages.value
  const cur = props.page
  if (tp <= 7) return Array.from({ length: tp }, (_, i) => i + 1)
  const arr = [1]
  const left = Math.max(2, cur - 1)
  const right = Math.min(tp - 1, cur + 1)
  if (left > 2) arr.push('...')
  for (let i = left; i <= right; i++) arr.push(i)
  if (right < tp - 1) arr.push('...')
  arr.push(tp)
  return arr
})

function go(p) {
  if (p < 1 || p > totalPages.value || p === props.page) return
  emit('update:page', p)
}
function onSize(s) {
  emit('update:pageSize', Number(s))
}
</script>
