<template>
  <div class="flex flex-col gap-4 lg:flex-1 lg:min-h-0">
    <!-- 工具条：行数上限 / 关键字 / 轮转开关 / 刷新。
         排障是「换关键字反复看原文」的循环，工具条常驻不随滚动消失。 -->
    <div class="dash-card fade-up shrink-0 p-3 sm:p-4">
      <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
        <div class="flex items-center gap-2">
          <span class="shrink-0 text-sm font-medium text-ink-soft">行数</span>
          <div class="w-28">
            <BaseSelect
              :model-value="String(store.tail)"
              :options="tailOptions"
              size="sm"
              @update:model-value="(v) => store.setFilters({ tail: Number(v) })"
            />
          </div>
        </div>

        <div class="flex min-w-56 flex-1 items-center gap-2 sm:max-w-md">
          <span class="shrink-0 text-sm font-medium text-ink-soft">关键字</span>
          <div class="relative w-full">
            <Icon
              name="search"
              :size="14"
              class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted"
            />
            <input
              :value="store.keyword"
              type="text"
              placeholder="按原文过滤，如 补跑 / 推送失败 / 任务 2151"
              class="h-8 w-full rounded-lg border border-ink/10 bg-elevated pl-8 pr-8 text-xs text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/10"
              @input="onKeywordInput"
            />
            <button
              v-if="store.keyword"
              type="button"
              class="absolute right-2 top-1/2 -translate-y-1/2 text-ink-muted transition hover:text-ink"
              aria-label="清除关键字"
              @click="store.setFilters({ keyword: '' })"
            >
              <Icon name="x-circle" :size="14" />
            </button>
          </div>
        </div>

        <label class="flex cursor-pointer items-center gap-2 text-sm text-ink-soft select-none">
          <BaseCheckbox :model-value="store.rotated" @update:model-value="(v) => store.setFilters({ rotated: v })" />
          并入轮转文件
        </label>

        <button
          type="button"
          class="ml-auto inline-flex items-center gap-1.5 rounded-xl border border-ink/10 bg-elevated px-3 py-1.5 text-sm font-medium text-ink-soft transition hover:border-brand/40 hover:text-brand disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="store.loading"
          @click="store.load()"
        >
          <Icon name="refresh" :size="14" :class="store.loading ? 'animate-spin' : ''" />
          刷新
        </button>

        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-xl border border-ink/10 bg-elevated px-3 py-1.5 text-sm font-medium text-ink-soft transition hover:border-brand/40 hover:text-brand disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="store.exporting"
          @click="onExport"
        >
          <Icon name="download" :size="14" :class="store.exporting ? 'animate-pulse' : ''" />
          导出
        </button>
      </div>

      <p class="mt-2 text-xs text-ink-muted">
        服务端运行日志（backend/logs/app.log）只读尾部，最新在前；调度执行、推送结果、对账补跑等过程日志都在这里。含轮转时按 app.log → app.log.1 → .2 → .3 新旧次序拼接。
      </p>
    </div>

    <!-- 日志正文：等宽字体全高滚动区。
         行是只读原文，不用表格——排障读的是带时间戳的叙事流，表格反而切割上下文。 -->
    <section class="dash-card fade-up relative flex min-h-0 flex-1 flex-col p-0">
      <div
        class="min-h-[320px] flex-1 overflow-auto rounded-2xl bg-ink/[0.03] p-4 lg:min-h-0"
        role="log"
        aria-label="运行日志内容"
      >
        <!-- 首载骨架 -->
        <div v-if="store.loading && !store.loaded" class="space-y-1.5">
          <div v-for="i in 12" :key="i" class="h-4 animate-pulse rounded bg-ink/5" :style="{ width: `${60 + ((i * 37) % 40)}%` }" />
        </div>

        <!-- 错误态：保留旧数据可继续看，错误条置顶 -->
        <div
          v-if="store.error"
          class="mb-3 flex items-center gap-2 rounded-lg border border-danger/20 bg-danger/[0.06] px-3 py-2 text-sm text-danger"
        >
          <Icon name="alert" :size="14" />
          {{ store.error }}
        </div>

        <ol v-if="store.items.length" class="space-y-0.5 font-mono text-xs leading-5">
          <li
            v-for="(it, idx) in store.items"
            :key="`${it.file}-${idx}`"
            class="group flex items-start gap-2 rounded px-1.5 py-0.5 transition hover:bg-elevated/80"
          >
            <!-- 徽标盒高 = 行盒高（h-5 对齐 leading-5）：首行视觉居中，折行后仍钉在首行 -->
            <span
              class="flex h-5 shrink-0 items-center rounded px-1 text-[10px] leading-none text-ink-muted/70"
              :class="it.file === 'app.log' ? 'bg-ink/5' : 'bg-amber/15 text-amber'"
              :title="it.file"
            >
              {{ it.file === 'app.log' ? '最新' : it.file.replace('app.', '') }}
            </span>
            <span class="min-w-0 break-all text-ink-soft [word-break:break-all]">{{ it.line }}</span>
          </li>
        </ol>

        <div v-else-if="store.loaded && !store.loading" class="grid h-full min-h-48 place-items-center text-sm text-ink-muted">
          {{ store.keyword ? '没有命中关键字的日志行' : '暂无日志' }}
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount } from 'vue'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import BaseCheckbox from '@/components/BaseCheckbox.vue'
import { useRuntimeLogsStore } from '@/stores/runtimeLogs'
import { toast } from '@/utils/toast'

const store = useRuntimeLogsStore()

const tailOptions = [
  { label: '300 行', value: '300' },
  { label: '800 行', value: '800' },
  { label: '2000 行', value: '2000' },
]

// 关键字防抖：排障敲的是长串关键字（任务号/错误片段），逐键请求纯属浪费
let kwTimer = null
function onKeywordInput(e) {
  const v = e.target.value
  clearTimeout(kwTimer)
  kwTimer = setTimeout(() => store.setFilters({ keyword: v.trim() }), 350)
}

// 导出当前筛选：命中 0 行时不生成空文件，直接提示
async function onExport() {
  try {
    const result = await store.exportLogs()
    if (!result) return
    if (!result.count) {
      toast('当前筛选下没有可导出的日志行', 'info')
      return
    }
    toast(`已导出 ${result.count} 行：${result.filename}`, 'success')
  } catch (e) {
    toast(e?.message || '导出失败，请稍后再试', 'error')
  }
}

onMounted(() => {
  store.load()
})

onBeforeUnmount(() => {
  clearTimeout(kwTimer)
  store.reset()
})
</script>
