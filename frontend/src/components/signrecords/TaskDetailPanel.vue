<template>
  <div>
    <div v-if="detail.loading" class="flex items-center justify-center py-8 text-sm text-ink-muted">
      加载详情中…
    </div>
    <div v-else-if="detail.error" class="py-2 text-sm text-danger">
      {{ detail.error }}
    </div>
    <div v-else class="space-y-4">
      <!-- 任务要素：列表详情展示；「正在进行」卡片行内已含这些字段，传 show-facts=false 省略 -->
      <div v-if="showFacts && row" data-detail-item class="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <div class="rounded-lg bg-elevated/70 px-2.5 py-2">
          <p class="text-[11px] text-ink-muted">日期</p>
          <p class="mt-0.5 truncate text-xs font-medium text-ink tabular-nums">
            {{ row.startDate }}<template v-if="row.endDate && row.endDate !== row.startDate"> ~ {{ row.endDate }}</template>
          </p>
        </div>
        <div class="rounded-lg bg-elevated/70 px-2.5 py-2">
          <p class="text-[11px] text-ink-muted">时段</p>
          <p class="mt-0.5 truncate text-xs font-medium text-ink tabular-nums">
            {{ row.startTime || '—' }}<template v-if="row.endTime"> – {{ row.endTime }}</template>
          </p>
        </div>
        <div class="rounded-lg bg-elevated/70 px-2.5 py-2">
          <p class="text-[11px] text-ink-muted">发起人</p>
          <p class="mt-0.5 truncate text-xs font-medium text-ink">{{ row.initiator || '—' }}</p>
        </div>
        <div class="rounded-lg bg-elevated/70 px-2.5 py-2">
          <p class="text-[11px] text-ink-muted">拍照要求</p>
          <p class="mt-0.5 truncate text-xs font-medium" :class="row.needPhoto ? 'text-amber' : 'text-ink'">
            {{ row.needPhoto ? '需拍照' : '无需拍照' }}
          </p>
        </div>
      </div>

      <!-- 地理围栏：一围栏一卡，多个自动排两列 -->
      <section data-detail-item>
        <h4 class="text-[11px] font-medium uppercase tracking-wide text-ink-muted">
          地理围栏（{{ fences.length }}）
        </h4>
        <div v-if="fences.length" class="mt-2 grid gap-2 sm:grid-cols-2">
          <article
            v-for="(g, gi) in fences"
            :key="gi"
            class="flex gap-2.5 rounded-xl border border-amber/20 bg-amber/5 p-2.5"
          >
            <svg width="34" height="34" viewBox="0 0 44 44" class="shrink-0" aria-hidden="true">
              <circle cx="22" cy="22" r="17" fill="none" stroke="#F2A65A" stroke-width="1.5" opacity="0.45" />
              <circle cx="22" cy="22" r="10" fill="none" stroke="#F2A65A" stroke-width="1.5" />
              <circle cx="22" cy="22" r="2.5" fill="#F2A65A" />
            </svg>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <span class="truncate text-sm font-medium text-ink" :title="g.alias">{{ g.alias || '未命名围栏' }}</span>
                <span class="shrink-0 rounded-full bg-amber/20 px-1.5 py-0.5 text-[10px] font-medium text-amber tabular-nums">
                  半径 {{ g.radius || '—' }}m
                </span>
              </div>
              <p class="mt-1 truncate text-[11px] tabular-nums text-ink-soft" :title="`${g.latitude || ''}, ${g.longitude || ''}`">
                {{ g.latitude || '—' }}, {{ g.longitude || '—' }}
              </p>
              <p class="mt-0.5 truncate text-[11px] text-ink-muted" :title="g.location">{{ g.location || '暂无地址' }}</p>
            </div>
          </article>
        </div>
        <p v-else class="mt-2 rounded-lg bg-elevated/70 px-2.5 py-2 text-xs text-ink-muted">该任务未设置地理围栏</p>
      </section>

      <!-- 签到凭证：一个任务只有一次签到，常态走单卡；多条仅作兜底 -->
      <section data-detail-item>
        <h4 class="text-[11px] font-medium uppercase tracking-wide text-ink-muted">签到凭证</h4>

        <article v-if="logs.length === 1" class="mt-2 flex items-start gap-3.5 rounded-xl border border-ink/5 bg-elevated p-3">
          <!-- 签到照片：点击全屏查看；无图时保持同尺寸占位，避免与右侧文字错位 -->
          <button
            v-if="logs[0].imageUrl && !brokenImgs.has(imgKey(logs[0]))"
            type="button"
            class="group/img relative h-24 w-24 shrink-0 overflow-hidden rounded-lg border border-ink/5 bg-cloud"
            title="点击全屏查看"
            @click="$emit('preview', logs[0])"
          >
            <img
              :src="logs[0].imageUrl"
              class="h-full w-full object-cover transition duration-300 group-hover/img:scale-105"
              loading="lazy"
              alt="签到图片"
              @error="onImgError(logs[0])"
            />
            <span class="absolute inset-0 grid place-items-center bg-black/0 opacity-0 transition group-hover/img:bg-black/25 group-hover/img:opacity-100">
              <Icon name="search" :size="18" class="text-white" />
            </span>
          </button>
          <div v-else class="grid h-24 w-24 shrink-0 place-items-center rounded-lg border border-dashed border-ink/10 bg-cloud text-[11px] text-ink-muted">
            无图
          </div>

          <div class="min-w-0 flex-1 space-y-1.5">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-semibold text-ink tabular-nums">{{ logs[0].time || '—' }}</span>
              <span class="shrink-0 rounded-full bg-success/10 px-2 py-0.5 text-[11px] font-medium text-success">已提交</span>
            </div>
            <p class="truncate text-xs text-ink-soft">
              {{ logs[0].studentName || '—' }}<template v-if="logs[0].studentNumber"> · {{ logs[0].studentNumber }}</template>
            </p>
            <p class="truncate text-xs text-ink-muted" :title="logs[0].location">
              定位 {{ logs[0].location || '—' }}
            </p>
            <p class="truncate text-xs text-ink-muted" :title="logs[0].remark">
              备注 {{ logs[0].remark || '无' }}
            </p>
          </div>
        </article>

        <!-- 兜底：一个任务出现多条记录时仍以紧凑列表呈现 -->
        <div v-else-if="logs.length > 1" class="mt-2 space-y-2">
          <div
            v-for="log in logs"
            :key="log.id"
            class="flex items-center gap-3 rounded-lg border border-ink/5 bg-elevated px-3 py-2"
          >
            <div class="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand/10 text-sm font-medium text-brand">
              {{ (log.studentName || '?').charAt(0) }}
            </div>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm text-ink">
                {{ log.studentName || '—' }}
                <span class="text-ink-muted">· {{ log.studentNumber || '—' }}</span>
              </p>
              <p class="truncate text-xs text-ink-muted tabular-nums">
                {{ log.time || '—' }} · 定位 {{ log.location || '—' }} · {{ log.remark || '无备注' }}
              </p>
            </div>
            <img
              v-if="log.imageUrl && !brokenImgs.has(imgKey(log))"
              :src="log.imageUrl"
              class="h-10 w-10 shrink-0 rounded-lg border border-ink/5 object-cover"
              loading="lazy"
              alt="签到图片"
              @error="onImgError(log)"
            />
            <span v-else class="shrink-0 text-[11px] text-ink-muted">无图</span>
          </div>
        </div>

        <!-- 无记录 -->
        <div v-else class="mt-2 flex items-center gap-2 rounded-xl border border-dashed border-danger/25 bg-danger/5 px-3 py-3 text-xs text-ink-muted">
          <Icon name="x-circle" :size="14" class="shrink-0 text-danger" />
          <span>{{ unsignedText }}</span>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  // { loading, error, geoFence, logs }
  detail: { type: Object, required: true },
  // 任务行（提供事实字段与图片失败去重键）
  row: { type: Object, default: null },
  // 是否展示「日期/时段/发起人/拍照要求」要素格（卡片行内已含，传 false）
  showFacts: { type: Boolean, default: true },
  // 无签到记录时的提示文案（历史=判漏签；进行中=尚未签到）
  unsignedText: { type: String, default: '该任务没有签到记录，判定为未签到' },
})

defineEmits(['preview'])

const fences = computed(() => props.detail?.geoFence || [])
const logs = computed(() => props.detail?.logs || [])

// 直连 B 平台的图片加载失败时回退为「无图」，按 任务-记录 维度去重
const brokenImgs = ref(new Set())
function imgKey(log) {
  return `${props.row?.id ?? 'x'}-${log.id}`
}
function onImgError(log) {
  brokenImgs.value = new Set(brokenImgs.value).add(imgKey(log))
}
</script>
