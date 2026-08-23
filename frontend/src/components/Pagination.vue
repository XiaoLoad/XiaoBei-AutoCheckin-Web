<template>
  <div class="flex flex-wrap items-center justify-between gap-3 text-sm">
    <!-- 总数 -->
    <div class="text-ink-muted">
      共 <span class="font-semibold text-ink tabular-nums">{{ total }}</span> 条
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <!-- 每页条数 -->
      <div class="flex items-center gap-1.5 text-ink-muted">
        <span>每页</span>
        <div class="w-20">
          <BaseSelect
            :model-value="pageSize"
            :options="pageSizeOptions"
            size="sm"
            :disabled="disabled"
            @update:model-value="onPageSizeChange"
          />
        </div>
        <span>条</span>
      </div>

      <!-- 上一页 -->
      <button
        type="button"
        :disabled="disabled || page <= 1"
        class="grid h-9 w-9 place-items-center rounded-lg border border-ink/10 text-ink-muted transition hover:bg-cloud hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-ink-muted"
        aria-label="上一页"
        @click="go(page - 1)"
      >
        <Icon name="chevron-left" :size="18" />
      </button>

      <!-- 页码窗口 -->
      <template v-for="(item, idx) in pageItems" :key="`${item}-${idx}`">
        <span v-if="item === '...'" class="px-1 text-ink-muted select-none">…</span>
        <button
          v-else
          type="button"
          :disabled="disabled"
          class="grid h-9 min-w-9 place-items-center rounded-lg border px-2 tabular-nums transition disabled:opacity-50"
          :class="item === page
            ? 'border-brand bg-brand font-semibold text-white'
            : 'border-ink/10 text-ink-soft hover:bg-cloud'"
          @click="go(item)"
        >
          {{ item }}
        </button>
      </template>

      <!-- 下一页 -->
      <button
        type="button"
        :disabled="disabled || page >= totalPages"
        class="grid h-9 w-9 rotate-180 place-items-center rounded-lg border border-ink/10 text-ink-muted transition hover:bg-cloud hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-ink-muted"
        aria-label="下一页"
        @click="go(page + 1)"
      >
        <Icon name="chevron-left" :size="18" />
      </button>

      <!-- 跳转指定页 -->
      <div class="flex items-center gap-1.5 text-ink-muted">
        <span>前往</span>
        <input
          v-model.number="jumpPage"
          type="number"
          min="1"
          :max="totalPages"
          :disabled="disabled"
          class="h-9 w-14 rounded-lg border border-ink/10 bg-white px-2 text-center text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10 disabled:opacity-50"
          @keyup.enter="onJump"
        />
        <span>页</span>
        <button
          type="button"
          :disabled="disabled"
          class="h-9 rounded-lg border border-ink/10 px-3 text-ink-soft transition hover:bg-cloud hover:text-ink disabled:opacity-50"
          @click="onJump"
        >
          确定
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'

// 通用分页组件：仅负责展示与翻页事件，不耦合任何业务数据。
// 父级通过 v-model:page 与 :page-size 传入状态，并监听 update:page / update:page-size 重新拉取数据。
const props = defineProps({
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 10 },
  total: { type: Number, default: 0 },
  pageSizeOptions: { type: Array, default: () => [10, 20, 50] },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['update:page', 'update:pageSize'])

const totalPages = computed(() => Math.max(1, Math.ceil((props.total || 0) / props.pageSize)))

// 窗口化页码：始终显示首页/末页，当前页附近展开 3 个，过长处以省略号折叠
const pageItems = computed(() => {
  const tp = totalPages.value
  const cur = props.page
  if (tp <= 7) return Array.from({ length: tp }, (_, i) => i + 1)
  const items = [1]
  const left = Math.max(2, cur - 1)
  const right = Math.min(tp - 1, cur + 1)
  if (left > 2) items.push('...')
  for (let i = left; i <= right; i++) items.push(i)
  if (right < tp - 1) items.push('...')
  items.push(tp)
  return items
})

const jumpPage = ref(props.page)
watch(
  () => props.page,
  (p) => {
    jumpPage.value = p
  }
)

function clamp(p) {
  return Math.min(totalPages.value, Math.max(1, p))
}

function go(p) {
  const next = clamp(p)
  if (next !== props.page) emit('update:page', next)
}

function onPageSizeChange(size) {
  const s = Number(size)
  emit('update:pageSize', s)
  emit('update:page', 1) // 改变每页条数时回到第一页
}

function onJump() {
  const p = Number(jumpPage.value)
  if (!Number.isFinite(p)) return
  go(p)
}
</script>
