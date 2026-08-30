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

      <div class="xb-scroll flex-1 min-h-0 space-y-6 overflow-y-auto px-5 py-5">
        <!-- ===== 关联配置摘要（只读瓦片） ===== -->
        <section>
          <div class="mb-2.5 flex items-center gap-2">
            <span class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">关联配置</span>
            <span class="h-px flex-1 bg-ink/10"></span>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div class="rounded-xl bg-cloud/60 px-3 py-2.5">
              <p class="text-[10px] uppercase tracking-wider text-ink-muted">配置套</p>
              <p class="mt-0.5 truncate text-xs font-medium text-ink" :title="configMeta.presetSetName">{{ configMeta.presetSetName }}</p>
            </div>
            <div class="rounded-xl bg-cloud/60 px-3 py-2.5">
              <p class="text-[10px] uppercase tracking-wider text-ink-muted">签到位置</p>
              <p class="mt-0.5 truncate text-xs font-medium text-ink" :title="configMeta.locationName">{{ configMeta.locationName }}</p>
            </div>
            <div class="rounded-xl bg-cloud/60 px-3 py-2.5">
              <p class="text-[10px] uppercase tracking-wider text-ink-muted">签到时段</p>
              <p class="mt-0.5 text-xs font-medium tabular-nums text-ink">
                {{ pad(configMeta.time?.startHour ?? '—') }}:00–{{ pad(configMeta.time?.endHour ?? '—') }}:00
              </p>
            </div>
            <div class="rounded-xl bg-cloud/60 px-3 py-2.5">
              <p class="text-[10px] uppercase tracking-wider text-ink-muted">定时时刻</p>
              <p class="mt-0.5 text-xs font-medium tabular-nums text-ink">
                {{ pad(configMeta.time?.signTime?.hour ?? 8) }}:{{ pad(configMeta.time?.signTime?.minute ?? 0) }}
              </p>
            </div>
          </div>
        </section>

        <!-- ===== 执行时间来源 ===== -->
        <section>
          <div class="mb-2.5 flex items-center gap-2">
            <span class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">执行时间来源</span>
            <span class="h-px flex-1 bg-ink/10"></span>
          </div>
          <div class="grid grid-cols-3 gap-2">
            <button
              type="button"
              class="rounded-xl border px-2 py-2.5 text-xs font-medium transition"
              :class="form.mode === 'follow' ? 'border-brand bg-brand/5 text-brand shadow-sm' : 'border-ink/10 text-ink-soft hover:bg-cloud'"
              @click="form.mode = 'follow'"
            >
              跟随配置套
            </button>
            <button
              v-if="isStandalone"
              type="button"
              class="rounded-xl border px-2 py-2.5 text-xs font-medium transition"
              :class="form.mode === 'standalone' ? 'border-brand bg-brand/5 text-brand shadow-sm' : 'border-ink/10 text-ink-soft hover:bg-cloud'"
              @click="form.mode = 'standalone'"
            >
              本任务配置
            </button>
            <button
              type="button"
              class="rounded-xl border px-2 py-2.5 text-xs font-medium transition"
              :class="form.mode === 'custom' ? 'border-brand bg-brand/5 text-brand shadow-sm' : 'border-ink/10 text-ink-soft hover:bg-cloud'"
              @click="form.mode = 'custom'"
            >
              自定义时刻
            </button>
          </div>
          <p class="mt-2 text-xs leading-relaxed text-ink-muted">{{ modeHint }}</p>
        </section>

        <!-- ===== 来源对应面板 ===== -->
        <section>
          <div class="mb-2.5 flex items-center gap-2">
            <span class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">触发计划</span>
            <span class="h-px flex-1 bg-ink/10"></span>
          </div>

          <!-- 跟随配置套：展示配置套的星期与时刻 -->
          <div v-if="form.mode === 'follow'" class="rounded-xl border border-brand/15 bg-brand/5 p-3.5 text-sm leading-relaxed text-ink-soft">
            <p class="flex items-center gap-1.5 font-medium text-brand">
              <Icon name="calendar" :size="13" />每周 {{ weekdayText }} {{ pad(configMeta.time?.signTime?.hour ?? 8) }}:{{ pad(configMeta.time?.signTime?.minute ?? 0) }} 起
            </p>
            <p class="mt-1.5 text-xs text-ink-muted">由配置套「{{ configMeta.presetSetName }}」决定；如需调整请修改配置套的定时与星期。</p>
          </div>

          <!-- 本任务配置（standalone）：展示任务快照的星期与时刻 -->
          <div v-else-if="form.mode === 'standalone'" class="rounded-xl border border-brand/15 bg-brand/5 p-3.5 text-sm leading-relaxed text-ink-soft">
            <p class="flex items-center gap-1.5 font-medium text-brand">
              <Icon name="calendar" :size="13" />每周 {{ standaloneWeekdayText }} {{ pad(configMeta.time?.signTime?.hour ?? 8) }}:{{ pad(configMeta.time?.signTime?.minute ?? 0) }} 起
            </p>
            <p class="mt-1.5 text-xs text-ink-muted">使用「账号任务配置」中保存的本任务配置；如需调整请前往该页修改后保存。</p>
          </div>

          <!-- 自定义时刻：时刻 + 星期 + 随机延时 -->
          <div v-else class="space-y-5">
            <div>
              <p class="mb-2 text-xs font-medium text-ink">每日执行时刻</p>
              <div class="flex items-center gap-2">
                <input
                  v-model.number="form.custom.hour"
                  type="number"
                  min="0"
                  max="23"
                  class="w-20 rounded-lg border border-ink/10 bg-white px-3 py-2 text-center text-sm tabular-nums text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/15"
                  @blur="clampNum('hour', 0, 23)"
                />
                <span class="text-ink-muted">:</span>
                <input
                  v-model.number="form.custom.minute"
                  type="number"
                  min="0"
                  max="59"
                  class="w-20 rounded-lg border border-ink/10 bg-white px-3 py-2 text-center text-sm tabular-nums text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/15"
                  @blur="clampNum('minute', 0, 59)"
                />
              </div>
            </div>

            <div>
              <p class="mb-2 text-xs font-medium text-ink">执行星期</p>
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
              <p class="mb-2 text-xs font-medium text-ink">随机延时上限（分钟）</p>
              <input
                v-model.number="form.custom.randomDelayMax"
                type="number"
                min="0"
                max="60"
                class="w-28 rounded-lg border border-ink/10 bg-white px-3 py-2 text-center text-sm tabular-nums text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/15"
                @blur="clampNum('randomDelayMax', 0, 60)"
              />
              <p class="mt-1.5 text-xs text-ink-muted">实际触发时间会在设定时刻基础上随机偏移，避免所有账号同一秒集中请求。</p>
            </div>
          </div>
        </section>

        <!-- ===== 下次执行预览 ===== -->
        <section>
          <div class="rounded-xl border border-brand/15 bg-gradient-to-br from-brand/[0.07] to-brand/[0.03] p-3.5">
            <p class="flex items-center gap-1.5 text-xs text-ink-muted">
              <Icon name="clock" :size="12" class="text-brand" />
              预计下一次执行
              <span class="text-ink-muted/60">（未保存改动的实时预览）</span>
            </p>
            <p class="mt-1 text-sm font-semibold text-brand">{{ previewText }}</p>
          </div>
        </section>
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
import { computeNextRun, formatNextRun, WEEKDAY_LABELS, pad } from '@/utils/schedule'

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

// 编辑副本：初始值取自当前调度任务（custom 字段可能为空，做兜底）
const safeCustom = props.schedule.custom || {}
const form = reactive({
  mode: props.schedule.mode,
  custom: {
    hour: typeof safeCustom.hour === 'number' ? safeCustom.hour : 8,
    minute: typeof safeCustom.minute === 'number' ? safeCustom.minute : 0,
    weekdays: Array.isArray(safeCustom.weekdays) ? [...safeCustom.weekdays] : [1, 2, 3, 4, 5, 6, 7],
    randomDelayMax: typeof safeCustom.randomDelayMax === 'number' ? safeCustom.randomDelayMax : 5
  }
})

// 独立配置任务：来源面板出现「本任务配置」档位
const isStandalone = computed(() => props.schedule.mode === 'standalone')
const modeHint = computed(() => {
  if (form.mode === 'follow') return '跟随配置套时，调度器按该配置套的定时与星期自动触发（带随机延时），无需单独设定。'
  if (form.mode === 'standalone') return '使用「账号任务配置」中保存的本任务配置触发；保存后切换到其它来源将改变执行时刻。'
  return '自定义每日时刻与星期，独立于配置套生效。'
})

const standaloneWeekdayText = computed(() => {
  const wd = configMeta.value?.time?.weekdays || []
  const labels = wd.map((d) => WEEKDAY_LABELS[d - 1]).filter(Boolean)
  return labels.length ? labels.join('、') : '未选择'
})
// 仅预览未保存的表单改动；线上展示走后端 nextRunAt（见 utils/schedule.js 头注释的职责边界）
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

const weekdayText = computed(() => {
  const wd = configMeta.value?.time?.weekdays || []
  const labels = wd.map((d) => WEEKDAY_LABELS[d - 1]).filter(Boolean)
  return labels.length ? labels.join('、') : '未选择'
})

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
