<template>
  <section class="dash-card fade-up shrink-0 overflow-hidden" aria-labelledby="active-tasks-heading">
    <!-- 头部：实时脉冲 + 标题 + 计数/空态；右侧更新时刻与刷新 -->
    <header class="flex items-center gap-2.5 px-4 py-2.5 sm:px-5">
      <span class="relative flex h-2.5 w-2.5 shrink-0" aria-hidden="true">
        <span class="absolute inline-flex h-full w-full rounded-full bg-success opacity-60 motion-safe:animate-ping" />
        <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-success" />
      </span>
      <h3 id="active-tasks-heading" class="shrink-0 text-sm font-semibold text-ink">正在进行</h3>

      <!-- 有任务：计数胶囊；无任务：安静的说明文字（不额外占高）；加载中：提示 -->
      <span
        v-if="!loadingActive && !activeError && activeTasks.length"
        class="shrink-0 rounded-full bg-brand/10 px-2 py-0.5 text-xs font-medium text-brand tabular-nums"
      >{{ activeTasks.length }} 项</span>
      <span
        v-else-if="!loadingActive && !activeError"
        class="min-w-0 flex-1 truncate text-xs text-ink-muted"
      >当前没有进行中的签到任务</span>
      <span v-else-if="loadingActive" class="text-xs text-ink-muted">读取中…</span>

      <div class="ml-auto flex shrink-0 items-center gap-2">
        <span
          v-if="updatedLabel"
          class="hidden text-[11px] tabular-nums sm:inline"
          :class="activeError ? 'text-amber' : 'text-ink-muted'"
          :title="activeError || `更新于 ${updatedLabel}`"
        >更新于 {{ updatedLabel }}</span>
        <button
          type="button"
          class="grid h-7 w-7 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="loadingActive || refreshingActive"
          title="刷新进行中任务"
          aria-label="刷新进行中任务"
          @click="refresh"
        >
          <Icon name="refresh" :size="14" :class="loadingActive || refreshingActive ? 'animate-spin' : ''" />
        </button>
      </div>
    </header>

    <!-- 首载骨架：与真实任务行同高，避免布局跳动 -->
    <div v-if="loadingActive" class="border-t border-ink/10 px-4 py-3 sm:px-5">
      <div class="flex items-center gap-3">
        <div class="h-8 w-1 rounded-full bg-ink/5 animate-pulse" />
        <div class="min-w-0 flex-1 space-y-2">
          <div class="h-4 w-40 rounded bg-ink/5 animate-pulse" />
          <div class="h-3 w-56 rounded bg-ink/5 animate-pulse" />
        </div>
        <div class="h-6 w-24 rounded-full bg-ink/5 animate-pulse" />
      </div>
    </div>

    <!-- 错误：内联提示 + 重试（请求已 silent，不走全局 toast） -->
    <div
      v-else-if="activeError && !activeTasks.length"
      class="flex items-center gap-2 border-t border-ink/10 px-4 py-3 text-xs text-ink-muted sm:px-5"
    >
      <Icon name="alert" :size="14" class="shrink-0 text-danger" />
      <span class="min-w-0 flex-1 truncate" :title="activeError">{{ activeError }}</span>
      <button type="button" class="shrink-0 rounded-md px-2 py-0.5 font-medium text-brand hover:bg-brand/10" @click="refresh">
        重试
      </button>
    </div>

    <!-- 进行中任务：类型色条区分寝/活，窗口进度条编码剩余时间 -->
    <ul
      v-else-if="rows.length"
      ref="listRef"
      class="divide-y divide-ink/5 border-t border-ink/10 transition-opacity duration-300"
      :class="refreshingActive && 'opacity-60'"
    >
      <li
        v-for="r in rows"
        :key="`${r.kind}-${r.id}`"
        data-active-row
        class="flex items-center gap-3 px-4 py-2.5 sm:px-5"
      >
        <span class="h-8 w-1 shrink-0 rounded-full" :class="typeRail(r.type)" />

        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span class="truncate text-sm font-semibold text-ink" :title="r.taskName">{{ r.taskName }}</span>
            <span class="shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium" :class="typeBadge(r.type).cls">
              {{ typeBadge(r.type).label }}
            </span>
            <span v-if="r.needPhoto" class="shrink-0 whitespace-nowrap rounded-full bg-amber/10 px-2 py-0.5 text-[11px] font-medium text-amber">需拍照</span>
          </div>
          <div class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-ink-muted">
            <span class="inline-flex items-center gap-1 tabular-nums">
              <Icon name="clock" :size="12" />{{ r._window }}
            </span>
            <span class="truncate">发起人 {{ r.initiator || '—' }}</span>
          </div>
          <div v-if="r._progress !== null" class="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-ink/10">
            <div
              class="h-full rounded-full transition-[width] duration-700 ease-out"
              :class="typeRail(r.type)"
              :style="{ width: r._progress + '%' }"
            />
          </div>
        </div>

        <span
          class="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold tabular-nums"
          :class="r._remain.cls"
        >
          <Icon name="clock" :size="12" />
          {{ r._remain.text }}
        </span>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { gsap } from 'gsap'
import { useSignRecordsStore } from '@/stores/signRecords'
import Icon from '@/components/Icon.vue'

const store = useSignRecordsStore()
const { activeTasks, loadingActive, refreshingActive, activeError, activeUpdatedAt } = storeToRefs(store)

const listRef = ref(null)
const reduceMotion = ref(false)
let mm = null
let lastSig = ''

// 走时：30s 一跳，驱动「剩余时间 / 窗口进度」；每 4 跳（120s）且页面可见时静默补一次数据。
// 后台刷新不登记全局 refreshBus——顶部进度条每 2 分钟闪一次是噪音，改由卡片自持指示。
const TICK_MS = 30000
const TICKS_PER_REFRESH = 4
const nowRef = ref(new Date())
let timer = null
let ticks = 0

function onTick() {
  nowRef.value = new Date()
  ticks += 1
  if (ticks % TICKS_PER_REFRESH === 0 && document.visibilityState === 'visible') refresh()
}

// 回到前台时数据若已陈旧（>60s）立即补一次，避免长时间隐藏后卡片停在旧快照
function onVisibility() {
  if (document.visibilityState !== 'visible') return
  nowRef.value = new Date()
  if (Date.now() - (activeUpdatedAt.value || 0) > 60000) refresh()
}

// 手动/自动刷新统一走静默：已有数据时保留列表原地换新（刷新按钮自旋 + 轻微降透明）
function refresh() {
  store.loadActiveTasks({ silent: true })
}

function pad(n) {
  return String(n).padStart(2, '0')
}
function fmtLocal(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

// 时间窗解析：缺字段兜底当天/全天；结束早于开始判为跨夜（次日）
function startEnd(t) {
  const sd = (t.startDate || '').slice(0, 10) || fmtLocal(new Date())
  const ed = (t.endDate || '').slice(0, 10) || sd
  const st = (t.startTime || '00:00').slice(0, 5)
  const et = (t.endTime || '23:59').slice(0, 5)
  const s = new Date(`${sd}T${st}:00`)
  let e = new Date(`${ed}T${et}:00`)
  if (isNaN(s) || isNaN(e)) return null
  if (e < s) e = new Date(e.getTime() + 86400000)
  return { s, e }
}

function windowText(t) {
  const st = (t.startTime || '').slice(0, 5)
  const et = (t.endTime || '').slice(0, 5)
  const sd = (t.startDate || '').slice(5)
  const ed = (t.endDate || t.startDate || '').slice(5)
  if (!et) return `${sd} ${st}`.trim()
  if (!sd || sd === ed) return `${st} – ${et}`
  return `${sd} ${st} – ${ed} ${et}`
}

function fmtDur(mins) {
  if (mins >= 60) {
    const h = Math.floor(mins / 60)
    const m = mins % 60
    return m ? `${h} 小时 ${m} 分` : `${h} 小时`
  }
  return `${mins} 分`
}

// 剩余时间与紧迫度：>30 分钟中性、≤30 分钟琥珀、≤10 分钟红；未开始/已结束各有措辞
function remainInfo(se, now) {
  if (!se) return { text: '进行中', cls: 'bg-cloud text-ink-soft' }
  if (now < se.s) {
    const m = Math.max(0, Math.ceil((se.s - now) / 60000))
    return { text: `${fmtDur(m)}后开始`, cls: 'bg-cloud text-ink-soft' }
  }
  if (now > se.e) return { text: '窗口已结束', cls: 'bg-danger/10 text-danger' }
  const mins = Math.max(0, Math.floor((se.e - now) / 60000))
  if (mins <= 10) return { text: `剩余 ${fmtDur(mins)}`, cls: 'bg-danger/10 text-danger' }
  if (mins <= 30) return { text: `剩余 ${fmtDur(mins)}`, cls: 'bg-amber/15 text-amber' }
  return { text: `剩余 ${fmtDur(mins)}`, cls: 'bg-cloud text-ink-soft' }
}

function typeBadge(t) {
  return t === 'activity'
    ? { label: '活动签到', cls: 'bg-info/10 text-info' }
    : { label: '寝室签到', cls: 'bg-brand/10 text-brand' }
}
function typeRail(t) {
  return t === 'activity' ? 'bg-info' : 'bg-brand'
}

// 富化一次：窗口文案 / 进度 / 剩余时间，随 nowRef 每 30s 重算，模板不再重复调用
const rows = computed(() =>
  activeTasks.value.map((t) => {
    const se = startEnd(t)
    const now = nowRef.value
    let progress = null
    if (se) {
      const total = se.e - se.s
      if (total > 0) progress = Math.min(100, Math.max(0, ((now - se.s) / total) * 100))
    }
    return { ...t, _window: windowText(t), _progress: progress, _remain: remainInfo(se, now) }
  })
)

const updatedLabel = computed(() => {
  const ts = activeUpdatedAt.value
  if (!ts) return ''
  const d = new Date(ts)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
})

function sigOf(list) {
  return list.map((t) => `${t.kind}-${t.id}`).join('|')
}

// 仅在任务集合真正变化时重放错落入场，后台静默刷新（数据未变）不触发，避免反复闪烁
async function animateRows() {
  await nextTick()
  const root = listRef.value
  if (!root || reduceMotion.value) return
  const rs = root.querySelectorAll('[data-active-row]')
  if (!rs.length) return
  gsap.fromTo(
    rs,
    { autoAlpha: 0, y: 8 },
    { autoAlpha: 1, y: 0, duration: 0.32, stagger: 0.05, ease: 'power2.out', overwrite: true, clearProps: 'opacity,transform' }
  )
}

watch(
  () => sigOf(activeTasks.value),
  (sig) => {
    if (sig === lastSig) return
    lastSig = sig
    animateRows()
  }
)

onMounted(() => {
  mm = gsap.matchMedia()
  mm.add('(prefers-reduced-motion: reduce)', () => {
    reduceMotion.value = true
    return () => {
      reduceMotion.value = false
    }
  })
  timer = setInterval(onTick, TICK_MS)
  document.addEventListener('visibilitychange', onVisibility)
  lastSig = sigOf(activeTasks.value)
  animateRows()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisibility)
  mm?.revert()
  gsap.killTweensOf(listRef.value?.querySelectorAll('[data-active-row]') || [])
})
</script>
