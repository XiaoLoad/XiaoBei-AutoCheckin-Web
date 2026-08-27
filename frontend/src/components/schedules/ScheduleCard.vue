<template>
  <article ref="root" class="sched-card dash-card relative flex flex-col overflow-hidden p-3">
    <!-- 左侧状态色条：开启时品牌蓝竖向铺满，GSAP 缩放呈现 -->
    <span
      ref="accent"
      class="pointer-events-none absolute left-0 top-0 h-full w-1 origin-top bg-brand"
      :class="schedule.enabled ? 'opacity-100' : 'opacity-0'"
    />

    <!-- 头部：账号 + 任务类型 + 开关 -->
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <span class="truncate text-sm font-semibold text-ink">{{ schedule.accountName }}</span>
          <span class="shrink-0 rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-medium text-brand">{{ schedule.taskLabel }}</span>
        </div>
        <p class="mt-1 truncate text-xs text-ink-muted">{{ schedule.platform }} · 学号 {{ schedule.studentNo }} · {{ schedule.className }}</p>
        <p class="mt-0.5 truncate text-xs text-ink-muted">关联「{{ configMeta.presetSetName }}」</p>
      </div>

      <!-- 自定义开关（GSAP 驱动滑块） -->
      <button
        type="button"
        role="switch"
        :aria-checked="schedule.enabled"
        :disabled="!schedule.accountEnabled || noConfigSet || switching"
        class="relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition-colors disabled:cursor-not-allowed"
        :class="schedule.enabled ? 'bg-brand' : 'bg-ink/15'"
        @click="$emit('toggle', schedule.id, !schedule.enabled)"
      >
        <span ref="knob" class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow" />
      </button>
    </div>

    <!-- 状态 + 下一次执行 -->
    <div class="mt-2.5 grid grid-cols-2 gap-2.5">
      <div>
        <p class="text-[11px] text-ink-muted">状态</p>
        <p class="mt-0.5 text-sm font-medium" :class="statusCls">{{ statusText }}</p>
      </div>
      <div>
        <p class="text-[11px] text-ink-muted">下一次执行</p>
        <p class="mt-0.5 text-sm font-medium text-ink">{{ nextRunText }}</p>
      </div>
    </div>

    <!-- 模式 chip + 上次运行 -->
    <div class="mt-2.5 flex items-center justify-between gap-2">
      <span class="inline-flex items-center gap-1 rounded-full bg-cloud px-2 py-0.5 text-[11px] text-ink-soft">
        <Icon name="clock" :size="12" />{{ modeText }}
      </span>
      <span class="truncate text-xs text-ink-muted">上次：{{ lastRunText }}</span>
    </div>

    <!-- 账号未启用提示 -->
    <p v-if="!schedule.accountEnabled" class="mt-1.5 text-[11px] text-warning">
      平台账号未启用，无法开启定时（请先在「账号管理」启用该账号）
    </p>

    <!-- 跟随配置套但未绑定配置套：无法开启 -->
    <p v-else-if="noConfigSet" class="mt-1.5 text-[11px] text-warning">
      未绑定配置套，无法开启（请先在「签到配置」绑定）
    </p>

    <!-- 操作 -->
    <div class="mt-auto flex items-center justify-end pt-2.5">
      <button
        type="button"
        class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-ink/10 px-3 text-sm font-medium text-ink-soft transition hover:bg-cloud"
        @click="$emit('open-settings', schedule)"
      >
        <Icon name="sliders" :size="14" />定时设置
      </button>
    </div>
  </article>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  schedule: { type: Object, required: true },
  configMeta: { type: Object, required: true }
})
defineEmits(['toggle', 'open-settings'])

const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const root = ref(null)
const accent = ref(null)
const knob = ref(null)
const switching = ref(false)

const statusText = computed(() => {
  if (!props.schedule.accountEnabled) return '账号未启用'
  return props.schedule.enabled ? '运行中' : '已暂停'
})
const statusCls = computed(() => {
  if (!props.schedule.accountEnabled) return 'text-warning'
  return props.schedule.enabled ? 'text-success' : 'text-ink-muted'
})
const modeText = computed(() => (props.schedule.mode === 'follow' ? '跟随配置套' : '自定义时刻'))
const noConfigSet = computed(() => props.schedule.mode === 'follow' && !props.schedule.configSetId)
const nextRunText = computed(() => {
  if (!props.schedule.enabled) return '未开启'
  return props.schedule.nextRunAt || '暂不可执行'
})
const lastRunText = computed(() => {
  const s = props.schedule
  if (!s.lastRun) return '暂无记录'
  const d = new Date(s.lastRun)
  const label = s.lastStatus === 'success' ? '成功' : s.lastStatus === 'fail' ? '失败' : s.lastStatus === 'skip' ? '跳过' : '—'
  const dot = s.lastStatus === 'success' ? 'text-success' : s.lastStatus === 'fail' ? 'text-danger' : 'text-ink-muted'
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${label} · ${hh}:${mm}`
})

// 开关/色条动画：enabled 变化时由 GSAP 平滑过渡
function animateState() {
  if (!knob.value || !accent.value) return
  const on = props.schedule.enabled
  if (prefersReduced) {
    gsap.set(knob.value, { x: on ? 20 : 5 })
    gsap.set(accent.value, { scaleY: on ? 1 : 0 })
    return
  }
  gsap.to(knob.value, { x: on ? 20 : 0, duration: 0.25, ease: 'power2.out' })
  gsap.to(accent.value, { scaleY: on ? 1 : 0, opacity: on ? 1 : 0, duration: 0.3, ease: 'power2.out' })
}

onMounted(async () => {
  await nextTick()
  if (knob.value) gsap.set(knob.value, { x: props.schedule.enabled ? 20 : 0 })
  if (accent.value) gsap.set(accent.value, { scaleY: props.schedule.enabled ? 1 : 0, opacity: props.schedule.enabled ? 1 : 0 })
})

watch(
  () => props.schedule.enabled,
  () => {
    switching.value = true
    animateState()
    setTimeout(() => (switching.value = false), 260)
  }
)
</script>
