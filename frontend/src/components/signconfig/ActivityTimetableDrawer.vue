<template>
  <Teleport to="body">
    <div ref="backdrop" class="fixed inset-0 z-40 flex justify-end bg-black/30 backdrop-blur-sm" @click.self="requestClose">
      <aside ref="panel" class="flex h-full w-full max-w-3xl flex-col bg-white shadow-2xl" role="dialog" aria-label="课表与调度">
        <!-- 头部：学期 + 同步 -->
        <header class="flex shrink-0 flex-wrap items-center gap-2 border-b border-ink/10 px-5 py-3.5">
          <div class="min-w-0 flex-1">
            <h3 class="text-base font-semibold text-ink">课表与调度</h3>
            <p class="mt-0.5 text-xs text-ink-muted">
              {{ semesterText }}
              <span v-if="overview?.timetableSyncedAt">· 同步于 {{ overview.timetableSyncedAt }}</span>
            </p>
          </div>
          <button
            type="button"
            class="inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-brand/30 px-3 text-sm font-medium text-brand transition hover:bg-brand/10 disabled:opacity-50"
            :disabled="isSyncing"
            @click="jwxtStore.sync(accountId)"
          >
            <Icon name="refresh" :size="13" />{{ isSyncing ? '同步中…' : '立即同步' }}
          </button>
          <button type="button" class="inline-flex h-8 shrink-0 items-center rounded-lg p-1.5 text-ink-muted transition hover:bg-cloud" aria-label="关闭" @click="requestClose">
            <Icon name="close" :size="16" />
          </button>
        </header>

        <!-- 周次切换 + 选中课程详情（面板置于滚动区之外：点任何色块，开关始终可见） -->
        <div class="shrink-0 border-b border-ink/5 px-5 py-2.5">
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-ink/10 text-xs text-ink-soft transition hover:bg-cloud disabled:opacity-40"
              aria-label="上一周"
              :disabled="week <= 1"
              @click="stepWeek(-1)"
            >‹</button>
            <div class="w-28 shrink-0">
              <BaseSelect v-model="week" :options="weekOptions" size="sm" numeric />
            </div>
            <button
              type="button"
              class="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-ink/10 text-xs text-ink-soft transition hover:bg-cloud disabled:opacity-40"
              aria-label="下一周"
              :disabled="week >= totalWeeks"
              @click="stepWeek(1)"
            >›</button>
            <span class="text-xs text-ink-muted">{{ weekRangeText }}</span>
            <span v-if="week === currentWeek" class="rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-medium text-brand">本周</span>
            <button
              v-else
              type="button"
              class="inline-flex h-7 items-center gap-1 whitespace-nowrap rounded-lg border border-brand/30 bg-brand/5 px-2.5 text-[11px] font-medium text-brand transition hover:bg-brand/10"
              @click="goCurrentWeek"
            >
              <Icon name="refresh" :size="12" />回到本周
            </button>
            <label class="ml-auto flex cursor-pointer items-center gap-1.5 text-xs text-ink-muted">
              <input v-model="showFaded" type="checkbox" class="h-3.5 w-3.5 accent-brand" />显示非本周
            </label>
          </div>
          <!-- 选中课程详情 + 参与调度开关（固定在网格上方，无需滚动） -->
          <div v-if="selected" ref="detailEl" class="mt-2.5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand/25 bg-brand/5 px-4 py-2.5">
            <div class="min-w-0 text-xs leading-relaxed text-ink-soft">
              <span class="text-sm font-semibold text-ink">{{ selected.course }}</span>
              <span class="ml-2">周{{ dayNames[selected.weekday - 1].label }} {{ selected.minSec }}-{{ selected.maxSec }}节（{{ blockTimeText(selected) }}）</span>
              <span class="ml-2 text-ink-muted">第{{ fmtWeeks(selected.weeks) }}周 · {{ selected.teacher || '教师待定' }}<template v-if="selected.room"> · {{ selected.room }}</template></span>
            </div>
            <label class="flex shrink-0 cursor-pointer items-center gap-2">
              <input
                type="checkbox"
                class="h-4 w-4 accent-brand"
                :checked="!isExcluded(selected)"
                @change="toggleBlock(selected)"
              />
              <span class="text-sm text-ink">参与自动签到</span>
            </label>
          </div>
        </div>

        <!-- 课表网格 -->
        <div class="xb-scroll min-h-0 flex-1 overflow-auto p-4">
          <p v-if="!overview?.bound" class="py-10 text-center text-sm text-ink-muted">请先绑定教务账号并同步课表</p>
          <p v-else-if="!periodRows.length" class="py-10 text-center text-sm text-ink-muted">暂无作息数据，请稍后重试</p>
          <div v-else class="grid min-w-[660px] gap-[3px]" :style="gridStyle">
            <!-- 表头（显式定位： sticky 置顶） -->
            <div class="tt-head corner"></div>
            <div
              v-for="d in dayNames"
              :key="'h' + d.day"
              class="tt-head"
              :style="{ gridColumn: String(d.day + 1), gridRow: '1' }"
            >
              周{{ d.label }}
              <span v-if="d.day === todayIsoweekday" class="tt-today-dot" title="今天"></span>
            </div>

            <!-- 时间列 + 背景格（全部显式定位，杜绝自动流被课程块挤位） -->
            <template v-for="p in periodRows" :key="'r' + p.idx">
              <div class="tt-time" :style="{ gridColumn: '1', gridRow: String(p.idx + 1) }">
                <b>{{ p.idx }}</b>
                <span>{{ p.start }}</span>
                <span>{{ p.end }}</span>
              </div>
              <div
                v-for="d in dayNames"
                :key="'s' + p.idx + '-' + d.day"
                class="tt-slot"
                :class="d.day === todayIsoweekday ? 'tt-slot-today' : ''"
                :style="{ gridColumn: String(d.day + 1), gridRow: String(p.idx + 1) }"
              ></div>
            </template>

            <!-- 课程块（显式定位 + GSAP 入场） -->
            <div
              v-for="b in displayBlocks"
              :key="b.blockKey + '-' + week"
              class="tt-block"
              :class="{
                'tt-block-faded': b.faded,
                'tt-block-excluded': isExcluded(b),
                'tt-block-selected': selectedKey === b.blockKey,
              }"
              :style="{ gridColumn: String(b.weekday + 1), gridRow: `${b.minSec + 1} / ${b.maxSec + 2}`, background: blockBackground(b) }"
              :title="`${b.course} · 周${dayNames[b.weekday - 1].label} ${b.minSec}-${b.maxSec}节（${blockTimeText(b)}）${isExcluded(b) ? ' · 已排除' : ''}`"
              @click="selectBlock(b)"
            >
              <div class="truncate font-semibold">{{ b.course }}</div>
              <div class="truncate text-white/90">{{ b.minSec }}-{{ b.maxSec }}节 · {{ blockTimeText(b) }}</div>
              <div v-if="b.room" class="truncate text-white/70">@{{ b.room }}</div>
              <span v-if="b.faded" class="tt-flag">非本周</span>
              <span v-else-if="isExcluded(b)" class="tt-flag">已排除</span>
            </div>
          </div>
        </div>

        <!-- 底部：排除统计 + 完成 -->
        <footer class="flex shrink-0 items-center justify-between gap-3 border-t border-ink/10 px-5 py-3.5">
          <span class="text-xs text-ink-muted">
            共 {{ courses.length }} 个时段 · 已排除 {{ excludedCount }} 个（改动随任务保存生效）
          </span>
          <button
            type="button"
            class="inline-flex h-9 items-center rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark"
            @click="requestClose"
          >
            完成
          </button>
        </footer>
      </aside>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import { useOverlayA11y } from '@/composables/useOverlayA11y'
import { useJwxtStore } from '@/stores/jwxt'

const props = defineProps({
  accountId: { type: String, required: true },
  // 任务配置草稿（excludeBlocks 直接写入，随「保存修改」持久化）
  config: { type: Object, required: true }
})
const emit = defineEmits(['close'])

const jwxtStore = useJwxtStore()
const REDUCED = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
const panel = ref(null)
const backdrop = ref(null)
const detailEl = ref(null)
const closing = ref(false)
const requestClose = () => {
  if (closing.value) return
  closing.value = true
  if (REDUCED || !panel.value) {
    emit('close')
    return
  }
  // 收起动画与定时任务抽屉同规格：面板滑出 + 遮罩淡出，完成后卸载
  gsap.to(backdrop.value, { opacity: 0, duration: 0.26, ease: 'power2.in' })
  gsap.to(panel.value, {
    xPercent: 100,
    duration: 0.28,
    ease: 'power3.in',
    onComplete: () => emit('close')
  })
}
useOverlayA11y(panel, requestClose)

const overview = computed(() => jwxtStore.overviewOf(props.accountId))
const courses = computed(() => overview.value?.courses || [])
const isSyncing = computed(() => !!jwxtStore.syncing[String(props.accountId || '')])
onMounted(() => {
  jwxtStore.load(props.accountId)
  if (REDUCED || !panel.value) return
  // 展开动画与定时任务抽屉同规格：遮罩淡入 + 面板自右滑入
  gsap.fromTo(backdrop.value, { opacity: 0 }, { opacity: 1, duration: 0.25, ease: 'power2.out' })
  gsap.fromTo(panel.value, { xPercent: 100 }, { xPercent: 0, duration: 0.32, ease: 'power3.out' })
})
onBeforeUnmount(() => {
  gsap.killTweensOf([panel.value, backdrop.value])
})

// ── 周次 ──
const DAY_MS = 86400000
const week1Monday = computed(() => {
  const s = overview.value?.semester?.week1Monday
  if (!s) return null
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
})
const totalWeeks = computed(() => overview.value?.semester?.totalWeeks || 25)
function weekOf(date) {
  const w1 = week1Monday.value
  if (!w1 || !date) return 0
  return Math.floor((date.getTime() - w1.getTime()) / DAY_MS / 7) + 1
}
const todayIsoweekday = computed(() => (new Date().getDay() === 0 ? 7 : new Date().getDay()))
const currentWeek = computed(() => {
  // 开学前的周日/假期周次算出 0 或越界时钳制到有效范围，保证"本周"徽标与回到本周按钮的状态一致
  return Math.min(totalWeeks.value, Math.max(1, weekOf(new Date(new Date().setHours(0, 0, 0, 0)))))
})
const week = ref(1)
// 学期数据到位后再定初始周（避免停留在默认第 1 周）
watch(week1Monday, () => { week.value = Math.max(1, currentWeek.value || 1) }, { immediate: true })
function stepWeek(delta) {
  week.value = Math.min(totalWeeks.value, Math.max(1, week.value + delta))
  animateBlocks()
}
// 周次下拉选项（1..总周数）
const weekOptions = computed(() =>
  Array.from({ length: totalWeeks.value }, (_, i) => ({ label: `第 ${i + 1} 周`, value: i + 1 }))
)
// 回到本周（跨周跳转后一键返回；与本周重合时不显示）
function goCurrentWeek() {
  week.value = Math.max(1, currentWeek.value || 1)
  animateBlocks()
}
const weekStart = computed(() => {
  const w1 = week1Monday.value
  if (!w1) return null
  const d = new Date(w1)
  d.setDate(d.getDate() + (week.value - 1) * 7)
  return d
})
const weekRangeText = computed(() => {
  const s = weekStart.value
  if (!s) return ''
  const e = new Date(s)
  e.setDate(e.getDate() + 6)
  const fmt = (x) => `${x.getMonth() + 1}.${String(x.getDate()).padStart(2, '0')}`
  return `${fmt(s)} ~ ${fmt(e)}`
})
const semesterText = computed(() => overview.value?.semester?.semester || '')
const dayNames = [
  { day: 1, label: '一' }, { day: 2, label: '二' }, { day: 3, label: '三' }, { day: 4, label: '四' },
  { day: 5, label: '五' }, { day: 6, label: '六' }, { day: 7, label: '日' }
]

// ── 作息表（后端生效配置）──
// 显示上限：实际课程最多到第 10 节（20:30 结束），11/12 节行不渲染；
// 若未来同步到更晚小节的课程，行数自动延展（取 max(10, 最大使用小节)）
const displayMaxPeriod = computed(() => {
  const used = courses.value.reduce((m, c) => Math.max(m, ...(c.sections || [0])), 0)
  return Math.max(10, used)
})
const periodRows = computed(() => {
  const pt = overview.value?.periodTimes || {}
  return Object.keys(pt).map((k) => ({ idx: Number(k), start: pt[k][0], end: pt[k][1] }))
    .filter((p) => p.idx <= displayMaxPeriod.value)
    .sort((a, b) => a.idx - b.idx)
})
const maxPeriod = computed(() => displayMaxPeriod.value)
const gridStyle = computed(() => ({
  gridTemplateColumns: '52px repeat(7, minmax(76px, 1fr))',
  gridTemplateRows: `26px repeat(${maxPeriod.value}, minmax(34px, auto))`
}))

// ── 课程块：本周实心；非本周淡显；与本周块时段冲突的非本周块不显示 ──
function overlap(a, b) {
  return Math.min(...a) <= Math.max(...b) && Math.min(...b) <= Math.max(...a)
}
const displayBlocks = computed(() => {
  const all = courses.value.map((c) => {
    const secs = c.sections || []
    return { ...c, minSec: Math.min(...secs), maxSec: Math.max(...secs) }
  })
  const solid = all.filter((c) => (c.weeks || []).includes(week.value))
  const out = [...solid]
  if (!showFaded.value) return out
  for (const c of all) {
    // 与已有块（本周实心或已加入的淡显块）时段冲突的不重复渲染，避免同格叠放
    if (out.some((o) => o.weekday === c.weekday && overlap(o.sections, c.sections))) continue
    out.push({ ...c, faded: true })
  }
  return out
})
const showFaded = ref(true)
watch(showFaded, () => animateBlocks())

// ── 块级排除（写入任务草稿 excludeBlocks，随保存生效） ──
const selectedKey = ref('')
const selected = computed(() => displayBlocks.value.find((b) => b.blockKey === selectedKey.value) || null)
function isExcluded(b) {
  return (props.config.activity?.course?.excludeBlocks || []).includes(b.blockKey)
}
function toggleBlock(b) {
  const course = props.config.activity?.course
  if (!course) return
  if (!Array.isArray(course.excludeBlocks)) course.excludeBlocks = []
  const i = course.excludeBlocks.indexOf(b.blockKey)
  if (i === -1) course.excludeBlocks.push(b.blockKey)
  else course.excludeBlocks.splice(i, 1)
}
const excludedCount = computed(() => (props.config.activity?.course?.excludeBlocks || []).length)

function selectBlock(b) {
  selectedKey.value = selectedKey.value === b.blockKey ? '' : b.blockKey
}
// 详情面板过渡：每次选中/切换/关闭都播放淡入上浮（含微缩放），替代突兀的瞬时出现
watch(selectedKey, () => {
  if (REDUCED || !selected.value) return
  nextTick(() => {
    if (!detailEl.value) return
    gsap.fromTo(
      detailEl.value,
      { autoAlpha: 0, y: 14, scale: 0.985 },
      { autoAlpha: 1, y: 0, scale: 1, duration: 0.32, ease: 'power3.out', clearProps: 'transform' }
    )
  })
})

// ── 展示辅助 ──
const PALETTE = ['#4f6ef2', '#2fb8a6', '#f0913a', '#e85d75', '#8b5cf6', '#0ea5e9', '#d946ef']
function colorOf(name) {
  let h = 0
  for (const ch of String(name)) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return PALETTE[h % PALETTE.length]
}
// 排除块去饱和呈现，与参与块拉开层次
function blockBackground(b) {
  return isExcluded(b) ? 'linear-gradient(135deg, #9aa3b2, #7c8698)' : colorOf(b.course)
}
function blockTimeText(b) {
  const pt = overview.value?.periodTimes || {}
  const s = pt[String(b.minSec)]
  const e = pt[String(b.maxSec)]
  return s && e ? `${s[0]}-${e[1]}` : ''
}
function fmtWeeks(weeks) {
  const a = [...(weeks || [])].sort((x, y) => x - y)
  const out = []
  let i = 0
  while (i < a.length) {
    let j = i
    while (j + 1 < a.length && a[j + 1] === a[j] + 1) j++
    out.push(i === j ? `${a[i]}` : `${a[i]}-${a[j]}`)
    i = j + 1
  }
  return out.join(',')
}

// ── GSAP：课程块错落淡入（挂载/换周/筛选变化时） ──
function animateBlocks() {
  if (REDUCED || !panel.value) return
  nextTick(() => {
    const els = panel.value.querySelectorAll('.tt-block')
    if (!els.length) return
    gsap.fromTo(
      els,
      { autoAlpha: 0, y: 8, scale: 0.96 },
      { autoAlpha: 1, y: 0, scale: 1, duration: 0.3, stagger: 0.04, ease: 'power2.out', clearProps: 'transform' }
    )
  })
}
watch([displayBlocks, periodRows], () => animateBlocks(), { flush: 'post' })
</script>

<style scoped>
.tt-head {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border-radius: 8px;
  background: #f2f4f9;
  padding: 4px 0;
  font-size: 12px;
  font-weight: 600;
  color: #4a5160;
}
.tt-head.corner {
  background: transparent;
}
.tt-today-dot {
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  background: var(--color-brand, #4f6ef2);
}
.tt-time {
  position: sticky;
  left: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #fff;
  font-size: 10px;
  line-height: 1.25;
  color: #8a93a3;
}
.tt-time b {
  font-size: 11px;
  color: #2b2f36;
}
.tt-slot {
  border-radius: 8px;
  background: #f6f7fb;
}
.tt-slot-today {
  background: #f0f3fd;
}
.tt-block {
  z-index: 5;
  overflow: hidden;
  border-radius: 10px;
  padding: 5px 6px;
  font-size: 11px;
  line-height: 1.35;
  color: #fff;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.18);
  transition: box-shadow 0.2s ease, filter 0.2s ease;
}
.tt-block:hover {
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.22);
  filter: brightness(1.05);
}
.tt-block-faded {
  opacity: 0.42;
  box-shadow: none;
}
.tt-block-excluded {
  filter: saturate(0.15);
}
.tt-block-excluded .truncate {
  text-decoration: line-through;
}
.tt-block-selected {
  outline: 2px solid #4f6ef2;
  outline-offset: 2px;
}
.tt-flag {
  display: inline-block;
  margin-top: 2px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.25);
  padding: 0 4px;
  font-size: 10px;
}
</style>
