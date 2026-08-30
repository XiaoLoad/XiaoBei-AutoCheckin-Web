<template>
  <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <!-- 左：数据概览 -->
    <div class="flex items-center gap-2 text-sm text-ink-muted">
      <span>共 {{ total }} 条</span>
      <span class="hidden text-ink/20 sm:inline">|</span>
      <span class="whitespace-nowrap">第 {{ page }} / {{ totalPages }} 页</span>
    </div>

    <!-- 右：每页条数 + 翻页 -->
    <div class="flex flex-wrap items-center justify-start gap-x-4 gap-y-2 sm:justify-end">
      <!-- 每页条数 -->
      <div class="flex items-center gap-1.5 text-sm text-ink-muted">
        <span class="whitespace-nowrap">每页</span>
        <div class="w-20">
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

      <!-- 翻页 -->
      <div class="inline-flex items-center rounded-xl bg-cloud p-1">
        <button
          type="button"
          class="grid h-8 w-8 place-items-center rounded-lg text-sm font-medium transition"
          :class="page <= 1 ? 'text-ink/30 cursor-not-allowed' : 'text-ink-muted hover:bg-white hover:text-ink'"
          :disabled="disabled || page <= 1"
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
          :disabled="disabled || page >= totalPages"
          aria-label="下一页"
          @click="go(page + 1)"
        >
          <Icon name="chevron-right" :size="16" />
        </button>

        <!-- 跳转指定页（可选，show-jump 开启；用户管理/账号管理等大数据量页面使用） -->
        <div v-if="showJump" class="flex items-center gap-1.5 pl-2 text-sm text-ink-muted">
          <span class="whitespace-nowrap">前往</span>
          <input
            v-model.number="jumpPage"
            type="number"
            min="1"
            :max="totalPages"
            :disabled="disabled"
            class="h-8 w-14 rounded-lg border border-ink/10 bg-white px-2 text-center text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10 disabled:opacity-50"
            @keyup.enter="onJump"
          />
          <span class="whitespace-nowrap">页</span>
          <button
            type="button"
            :disabled="disabled"
            class="h-8 rounded-lg px-2 text-sm font-medium text-ink-soft transition hover:bg-white hover:text-ink disabled:opacity-50"
            @click="onJump"
          >
            确定
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import BaseSelect from '@/components/BaseSelect.vue'
import Icon from '@/components/Icon.vue'

// 全站唯一分页组件（原 Pagination.vue 已收编删除；跳页框经 show-jump 按需开启）。
// 仅负责展示与翻页事件，不耦合任何业务数据；
// 父级通过 :page / :page-size 传入状态，并监听 update:page / update:page-size 重新拉取数据。
// [约定] 改变每页条数后回到第一页由调用方 handler 负责：本组件不代发 update:page(1)，
// 否则服务端分页的调用方（page/pageSize 各触发一次请求）一次改页码会拉两次数据。
const props = defineProps({
  page: { type: Number, required: true },
  pageSize: { type: Number, required: true },
  total: { type: Number, required: true },
  pageSizeOptions: { type: Array, default: () => [10, 20, 50] },
  disabled: { type: Boolean, default: false },
  showJump: { type: Boolean, default: false }
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

const jumpPage = ref(props.page)
watch(
  () => props.page,
  (p) => {
    jumpPage.value = p
  }
)

function go(p) {
  if (p < 1 || p > totalPages.value || p === props.page) return
  emit('update:page', p)
}
function onSize(s) {
  emit('update:pageSize', Number(s))
}
function onJump() {
  const p = Number(jumpPage.value)
  if (!Number.isFinite(p)) return
  go(p)
}
</script>
