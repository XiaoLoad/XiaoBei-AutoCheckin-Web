<template>
  <div class="fixed inset-0 z-50">
    <!-- 遮罩 -->
    <div ref="overlay" class="absolute inset-0 bg-ink/40" @click="requestClose" />

    <!-- 右滑抽屉面板 -->
    <aside
      ref="panel"
      class="absolute right-0 top-0 flex h-full w-full max-w-md flex-col bg-white shadow-2xl"
      role="dialog"
      aria-modal="true"
    >
      <header class="flex shrink-0 items-center justify-between border-b border-ink/10 px-5 py-4">
        <div class="min-w-0">
          <h3 class="text-base font-semibold text-ink">定时设置</h3>
          <p class="mt-0.5 truncate text-xs text-ink-muted">{{ schedule.accountName }} · {{ schedule.taskLabel }}</p>
        </div>
        <button type="button" class="grid h-9 w-9 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud" aria-label="关闭" @click="requestClose">
          <Icon name="close" :size="20" />
        </button>
      </header>

      <div class="xb-scroll flex-1 min-h-0 space-y-5 overflow-y-auto px-5 py-4">
        <!-- 关联配置摘要（只读） -->
        <div class="rounded-xl bg-cloud/60 p-3 text-xs leading-relaxed text-ink-soft">
          关联配置套「<span class="font-medium text-ink">{{ configMeta.presetSetName }}</span>」· 位置「<span class="font-medium text-ink">{{ configMeta.locationName }}</span>」· 时段
          <span class="font-medium text-ink">{{ configMeta.time?.startHour ?? '—' }}:00–{{ configMeta.time?.endHour ?? '—' }}:00</span>
          · 定时 <span class="font-medium text-ink">{{ pad(configMeta.time?.signTime?.hour ?? 8) }}:{{ pad(configMeta.time?.signTime?.minute ?? 0) }}</span>
        </div>

        <!-- 执行时间来源 -->
        <div>
          <p class="mb-2 text-sm font-medium text-ink">执行时间来源</p>
          <div class="grid grid-cols-2 gap-2">
            <button
              type="button"
              class="rounded-xl border px-3 py-2.5 text-sm font-medium transition"
              :class="form.mode === 'follow' ? 'border-brand bg-brand/5 text-brand' : 'border-ink/10 text-ink-soft hover:bg-cloud'"
              @click="form.mode = 'follow'"
            >
              跟随配置套
            </button>
            <button
              type="button"
              class="rounded-xl border px-3 py-2.5 text-sm font-medium transition"
              :class="form.mode === 'custom' ? 'border-brand bg-brand/5 text-brand' : 'border-ink/10 text-ink-soft hover:bg-cloud'"
              @click="form.mode = 'custom'"
            >
              自定义时刻
            </button>
          </div>
          <p class="mt-2 text-xs text-ink-muted">
            跟随配置套时，调度器会按该配置套的星期与起始小时自动触发（带随机延时），无需单独设定。
          </p>
        </div>

        <!-- 跟随预览 -->
        <div v-if="form.mode === 'follow'" class="rounded-xl border border-ink/10 bg-white p-3 text-sm text-ink-soft">
          {{ followText }}
        </div>

        <!-- 自定义输入 -->
        <div v-else class="space-y-4">
          <div>
            <p class="mb-1.5 text-sm font-medium text-ink">每日执行时刻</p>
            <div class="flex items-center gap-2">
              <input
                v-model.number="form.custom.hour"
                type="number"
                min="0"
                max="23"
                class="w-20 rounded-lg border border-ink/10 px-3 py-2 text-center text-sm tabular-nums focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/15"
                @blur="clampNum('hour', 0, 23)"
              />
              <span class="text-ink-muted">:</span>
              <input
                v-model.number="form.custom.minute"
                type="number"
                min="0"
                max="59"
                class="w-20 rounded-lg border border-ink/10 px-3 py-2 text-center text-sm tabular-nums focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/15"
                @blur="clampNum('minute', 0, 59)"
              />
            </div>
          </div>

          <div>
            <p class="mb-1.5 text-sm font-medium text-ink">执行星期</p>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="(w, idx) in 7"
                :key="w"
                type="button"
                class="h-9 w-9 rounded-lg border text-sm font-medium transition"
                :class="isWeekday(idx + 1) ? 'border-brand bg-brand/5 text-brand' : 'border-ink/10 text-ink-soft hover:bg-cloud'"
                @click="toggleWeekday(idx + 1)"
              >
                {{ weekdayLabel(idx) }}
              </button>
            </div>
          </div>

          <div>
            <p class="mb-1.5 text-sm font-medium text-ink">随机延时上限（分钟）</p>
            <input
              v-model.number="form.custom.randomDelayMax"
              type="number"
              min="0"
              max="60"
              class="w-28 rounded-lg border border-ink/10 px-3 py-2 text-center text-sm tabular-nums focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/15"
              @blur="clampNum('randomDelayMax', 0, 60)"
            />
            <p class="mt-1.5 text-xs text-ink-muted">实际触发时间会在设定时刻前后随机偏移，避免所有账号同一秒集中请求。</p>
          </div>
        </div>

        <!-- 下次执行预览 -->
        <div class="rounded-xl bg-brand/5 p-3">
          <p class="mb-1 text-xs text-ink-muted">预计下一次执行</p>
          <p class="text-sm font-semibold text-brand">{{ previewText }}</p>
        </div>
      </div>

      <footer class="flex shrink-0 items-center justify-end gap-2 border-t border-ink/10 px-5 py-4">
        <button type="button" class="inline-flex h-9 items-center rounded-lg border border-ink/10 px-4 text-sm font-medium text-ink-soft transition hover:bg-cloud" @click="requestClose">
          取消
        </button>
        <button type="button" class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50" :disabled="saving" @click="save">
          <Icon name="check" :size="14" />{{ saving ? '保存中…' : '保存' }}
        </button>
      </footer>
    </aside>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { computeNextRun, formatNextRun, nextRunSummary, WEEKDAY_LABELS, pad } from '@/utils/schedule'

const props = defineProps({
  schedule: { type: Object, required: true },
  saving: { type: Boolean, default: false }
})
const emit = defineEmits(['save', 'close'])

const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const overlay = ref(null)
const panel = ref(null)
const closing = ref(false)

const signConfigStore = useSignConfigStore()
const configMeta = computed(() =>
  signConfigStore.taskConfigMetaOf(props.schedule.accountId, props.schedule.taskType)
)

// 编辑副本：初始值取自当前调度任务
const form = reactive({
  mode: props.schedule.mode,
  custom: { ...props.schedule.custom, weekdays: [...props.schedule.custom.weekdays] }
})

const followText = computed(() => nextRunSummary('follow', form.custom, configMeta))
const previewText = computed(() => {
  const date = computeNextRun(form.mode, form.custom, configMeta)
  return formatNextRun(date).text
})

function weekdayLabel(idx) {
  return WEEKDAY_LABELS[idx]
}
function isWeekday(d) {
  return form.custom.weekdays.includes(d)
}
function toggleWeekday(d) {
  const i = form.custom.weekdays.indexOf(d)
  if (i === -1) form.custom.weekdays.push(d)
  else form.custom.weekdays.splice(i, 1)
  form.custom.weekdays.sort((a, b) => a - b)
}
function clampNum(key, min, max) {
  let v = Number(form.custom[key])
  if (Number.isNaN(v)) v = min
  v = Math.min(max, Math.max(min, Math.round(v)))
  form.custom[key] = v
}

function save() {
  emit('save', props.schedule.id, { mode: form.mode, custom: { ...form.custom, weekdays: [...form.custom.weekdays] } })
  requestClose()
}

function requestClose() {
  if (closing.value) return
  closing.value = true
  if (prefersReduced || !panel.value) {
    emit('close')
    return
  }
  gsap.to(overlay.value, { opacity: 0, duration: 0.26, ease: 'power2.in' })
  gsap.to(panel.value, {
    xPercent: 100,
    duration: 0.28,
    ease: 'power3.in',
    onComplete: () => emit('close')
  })
}

onMounted(() => {
  if (prefersReduced || !panel.value) return
  gsap.fromTo(overlay.value, { opacity: 0 }, { opacity: 1, duration: 0.25, ease: 'power2.out' })
  gsap.fromTo(panel.value, { xPercent: 100 }, { xPercent: 0, duration: 0.32, ease: 'power3.out' })
})

onBeforeUnmount(() => {
  gsap.killTweensOf([panel.value, overlay.value])
})
</script>

<style scoped>
.xb-scroll {
  scrollbar-gutter: stable;
}
</style>
