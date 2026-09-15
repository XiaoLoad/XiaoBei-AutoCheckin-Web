<template>
  <section class="dash-card fade-up shrink-0 overflow-hidden" aria-labelledby="active-tasks-heading">
    <!-- 头部：实时脉冲 + 标题 + 计数/空态；右侧更新时刻与刷新 -->
    <header class="flex items-center gap-2.5 px-4 py-2.5 sm:px-5">
      <span class="relative flex h-2.5 w-2.5 shrink-0" aria-hidden="true">
        <span class="absolute inline-flex h-full w-full rounded-full bg-success opacity-60 motion-safe:animate-ping" />
        <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-success" />
      </span>
      <h3 id="active-tasks-heading" class="shrink-0 text-sm font-semibold text-ink">正在进行</h3>

      <!-- 有任务：分桶计数（当前类型筛选命中者高亮），胶囊本身即类型筛选开关——
           点一下只看该类，再点一下取消回全部；计数为 0 时不可点（点了也是空列表）。
           它同时是筛选后列表为空时唯一的兜底信息来源 -->
      <template v-if="!loadingActive && !activeError && activeTasks.length">
        <button
          v-for="b in buckets"
          :key="`bk-${b.type}`"
          type="button"
          class="shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium tabular-nums transition disabled:cursor-default"
          :class="bucketCls(b)"
          :disabled="!b.count"
          :aria-pressed="typeFilter === b.type"
          :title="bucketTitle(b)"
          @click="toggleBucket(b)"
        >{{ b.label }} {{ b.count }}</button>
      </template>
      <!-- 无任务：安静的说明文字，不额外占高 -->
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

    <!-- 筛选后为空、但另一类型还有任务：必须把这条兜出来，否则用户切到空类型会
         误以为「完全没任务」而漏签——这正是这张卡片存在的意义 -->
    <div
      v-else-if="!rows.length && otherBucket"
      class="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-ink/10 px-4 py-3 text-xs text-ink-muted sm:px-5"
    >
      <Icon name="info" :size="14" class="shrink-0 text-ink-muted" />
      <span class="min-w-0 flex-1">当前没有进行中的{{ shortLabel(typeFilter) }}签到任务</span>
      <button
        type="button"
        class="shrink-0 rounded-md px-2 py-0.5 font-medium text-brand transition hover:bg-brand/10"
        @click="store.setType(otherBucket.type)"
      >切到{{ otherBucket.label }}（{{ otherBucket.count }} 项）</button>
    </div>

    <!-- 进行中任务：类型色条区分寝/活，窗口进度条编码剩余时间 -->
    <ul
      v-else-if="rows.length"
      ref="listRef"
      class="divide-y divide-ink/5 border-t border-ink/10 transition-opacity duration-300"
      :class="refreshingActive && 'opacity-60'"
    >
      <li v-for="r in rows" :key="`${r.kind}-${r.id}`" data-active-row>
        <button
          type="button"
          class="flex w-full items-center gap-3 px-4 py-2.5 text-left transition hover:bg-cloud/40 sm:px-5"
          :aria-expanded="detailOpen(r.id)"
          @click="store.toggleExpand(r)"
        >
          <span class="h-8 w-1 shrink-0 rounded-full" :class="taskTypeMeta(r.type).solid" />

          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span class="truncate text-sm font-semibold text-ink" :title="r.taskName">{{ r.taskName }}</span>
              <span class="shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium" :class="taskTypeMeta(r.type).cls">
                {{ taskTypeMeta(r.type).label }}
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
                :class="taskTypeMeta(r.type).solid"
                :style="{ width: r._progress + '%' }"
              />
            </div>
          </div>

          <!-- 状态：已签到 → 绿色状态胶囊；待签到 → 剩余时间（紧迫度分档） -->
          <span
            class="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold tabular-nums"
            :class="statusInfo(r).cls"
          >
            <Icon :name="r.finished ? 'check-circle' : 'clock'" :size="12" />
            {{ statusInfo(r).text }}
          </span>

          <Icon
            name="chevron-right"
            :size="18"
            class="shrink-0 text-ink-muted transition-transform"
            :class="detailOpen(r.id) ? 'rotate-90' : ''"
          />
        </button>

        <!-- 展开：地理围栏 + 签到凭证（与历史列表详情共用面板） -->
        <Transition :css="false" @enter="onDetailEnter" @leave="onDetailLeave">
          <div v-if="detailOpen(r.id)" class="overflow-hidden border-t border-ink/5 bg-cloud/30 px-3 py-3 sm:px-5">
            <TaskDetailPanel
              :detail="store.getDetail(r.id)"
              :row="r"
              :show-facts="false"
              unsigned-text="尚未签到，可在任务时段内完成"
              @preview="emit('preview', $event)"
            />
          </div>
        </Transition>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { gsap } from 'gsap'
import { useSignRecordsStore } from '@/stores/signRecords'
import { taskTypeMeta } from '@/utils/accountType'
import Icon from '@/components/Icon.vue'
import TaskDetailPanel from '@/components/signrecords/TaskDetailPanel.vue'
import { useCollapseTransition } from '@/composables/useCollapseTransition'

const emit = defineEmits(['preview'])

const store = useSignRecordsStore()
const { activeTasks, loadingActive, refreshingActive, activeError, activeUpdatedAt, typeFilter } = storeToRefs(store)

const listRef = ref(null)
const reduceMotion = ref(false)
let mm = null
let lastSig = ''

// 走时：30s 一跳，驱动「剩余时间 / 窗口进度」；每 4 跳（120s）且页面可见时静默补一次数据。
// 后台自动刷新不亮全局进度条（每 2 分钟闪一次是噪音），由卡片自持指示（刷新键自旋 + 「更新于」）。
const TICK_MS = 30000
const TICKS_PER_REFRESH = 4
const nowRef = ref(new Date())
let timer = null
let ticks = 0

function onTick() {
  nowRef.value = new Date()
  ticks += 1
  if (ticks % TICKS_PER_REFRESH === 0 && document.visibilityState === 'visible') refreshInBackground()
}

// 回到前台时数据若已陈旧（>60s）立即补一次，避免长时间隐藏后卡片停在旧快照
function onVisibility() {
  if (document.visibilityState !== 'visible') return
  nowRef.value = new Date()
  if (Date.now() - (activeUpdatedAt.value || 0) > 60000) refreshInBackground()
}

// 手动刷新：静默换新（列表原地保留、刷新键自旋），并照常亮全局进度条
function refresh() {
  store.loadActiveTasks({ silent: true })
}

// 后台自动刷新：同样静默，但向请求层声明 skipLoadingBar，不参与全局加载条
function refreshInBackground() {
  store.loadActiveTasks({ silent: true, background: true })
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

function shortLabel(t) {
  return taskTypeMeta(t).short
}

// 分桶计数：头部始终给出寝/活各自的数量（而非单一总数），
// 这样即便当前筛选把某一类隐藏了，用户仍知道另一类有没有待签任务
const buckets = computed(() =>
  ['dorm', 'activity'].map((t) => ({
    type: t,
    label: shortLabel(t),
    count: activeTasks.value.filter((r) => r.type === t).length,
  }))
)
// 当前筛选未命中、但确实有任务的另一类：仅在「筛选后列表为空」时用于提示
const otherBucket = computed(() =>
  buckets.value.find((b) => b.type !== typeFilter.value && b.count > 0) || null
)
function bucketCls(b) {
  if (!b.count) return 'bg-cloud text-ink-muted'
  // 未筛选（两类都在看）或命中当前筛选 → 用自身类型色；被筛选排除的那一类退为中性，
  // 用颜色差异表达「列表已按类型收窄」，避免用户以为另一类的任务消失了
  const shown = typeFilter.value === 'all' || typeFilter.value === b.type
  return shown ? taskTypeMeta(b.type).cls : 'bg-cloud text-ink-soft'
}
function bucketTitle(b) {
  if (!b.count) return `${b.label}签到：当前没有进行中的任务`
  return typeFilter.value === b.type
    ? `${b.label}签到 ${b.count} 项 · 点击取消筛选，回到全部`
    : `${b.label}签到 ${b.count} 项 · 点击只看${b.label}`
}
// 胶囊即筛选开关：命中者再点一下回「全部」，与上方筛选栏共用 store.typeFilter 这一个状态，
// 两处不会不同步。计数为 0 时按钮 disabled，避免点进一个必然为空的列表。
function toggleBucket(b) {
  if (!b.count) return
  store.setType(typeFilter.value === b.type ? 'all' : b.type)
}

// 卡片只跟随「签到类型」筛选：数据仍是全量（寝+活），在本地按 typeFilter 过滤，
// 切换零请求、零延迟。status/日期/视图模式明确不作用于卡片——卡片的价值是
// 「本时段签没签完」，按未签到去筛会把已签到的行筛掉，反而丢掉「已完成」这个信号。
const visibleTasks = computed(() =>
  typeFilter.value === 'all'
    ? activeTasks.value
    : activeTasks.value.filter((r) => r.type === typeFilter.value)
)

// 展开状态与状态胶囊：已签到固定展示绿色状态，未签到展示剩余时间（紧迫度分档）
function detailOpen(id) {
  const d = store.getDetail(id)
  return !!(d && d.open)
}
function statusInfo(r) {
  return r.finished ? { text: '已签到', cls: 'bg-success/10 text-success' } : r._remain
}

// 详情折叠补间（与历史列表详情共用组合式）
const { onEnter: onDetailEnter, onLeave: onDetailLeave } = useCollapseTransition(
  () => reduceMotion.value,
  { pad: 12 } // 与卡片详情 py-3 对齐
)

// 富化一次：窗口文案 / 进度 / 剩余时间，随 nowRef 每 30s 重算，模板不再重复调用
const rows = computed(() =>
  visibleTasks.value.map((t) => {
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

// 签名取自「可见行」而非全量数据：切换类型筛选后可见集合变了，理应重放一次入场；
// 而后台静默刷新若数据未变（签名不变）不触发，避免每 2 分钟闪一次。
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
  () => sigOf(rows.value),
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
  lastSig = sigOf(rows.value)
  animateRows()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisibility)
  mm?.revert()
  gsap.killTweensOf(listRef.value?.querySelectorAll('[data-active-row]') || [])
})
</script>
