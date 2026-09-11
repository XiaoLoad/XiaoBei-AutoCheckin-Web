<template>
  <div ref="root" :class="block ? 'relative block w-full' : 'relative inline-block'">
    <!-- 触发器：与同轨的分段按钮等高（h-[30px]），宽度由日期文本决定，不再占两格原生输入框。
         block 形态（弹窗内的独立表单字段）改为撑满并带上输入框外形——无边框的紧凑触发器
         放在工具栏轨道里合适，孤零零躺在表单标签下会像一行普通文字，看不出可以点 -->
    <div
      class="flex items-center gap-0.5 transition"
      :class="[
        block ? 'relative w-full' : 'rounded-lg',
        !block && open ? 'bg-white shadow-sm ring-1 ring-ink/5' : '',
      ]"
    >
      <button
        ref="trigger"
        type="button"
        class="flex items-center gap-1.5 font-medium transition disabled:cursor-not-allowed disabled:opacity-50"
        :class="block
          ? [
              'h-10 w-full justify-start rounded-xl border px-3 pr-10 text-sm',
              open
                ? 'border-brand bg-white text-ink ring-4 ring-brand/15'
                : 'border-ink/10 bg-cloud/70 hover:border-ink/20',
              hasValue ? 'text-ink' : 'text-ink-muted',
              'focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/15',
            ]
          : [
              'h-[30px] rounded-lg px-2 text-[13px]',
              open || hasValue ? 'bg-white text-ink shadow-sm ring-1 ring-ink/5' : 'text-ink-muted hover:text-ink-soft',
              open ? 'ring-brand/30' : '',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30',
            ]"
        aria-haspopup="dialog"
        :aria-expanded="open"
        :aria-label="range ? '选择日期范围' : '选择日期'"
        :disabled="disabled"
        @click="toggle"
      >
        <Icon name="calendar" :size="14" class="shrink-0 text-ink-muted" />
        <span class="whitespace-nowrap tabular-nums" :class="hasValue ? '' : 'font-normal'">{{ displayText }}</span>
      </button>
      <button
        v-if="hasValue && !disabled"
        type="button"
        class="grid h-5 w-5 shrink-0 place-items-center rounded-md text-ink-muted transition hover:bg-cloud hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
        :class="block ? 'absolute right-3 top-1/2 -translate-y-1/2' : ''"
        aria-label="清除日期"
        @click.stop="clear"
      >
        <Icon name="close" :size="13" />
      </button>
    </div>

    <!-- 面板：Teleport 到 body，脱离滚动容器，展开时不撑大页面 -->
    <Teleport to="body">
      <Transition name="xb-pop">
        <div
          v-if="open"
          ref="panel"
          class="fixed z-[1000] w-[280px] rounded-2xl border border-ink/10 bg-white p-3 shadow-xl shadow-ink/10"
          role="dialog"
          :aria-label="range ? '选择日期范围' : '选择日期'"
          :style="panelStyle"
        >
          <!-- 月份导航 -->
          <div class="flex items-center justify-between">
            <button
              type="button"
              class="grid h-7 w-7 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
              aria-label="上个月"
              @click="shiftMonth(-1)"
            >
              <Icon name="chevron-left" :size="16" />
            </button>
            <span class="text-[13px] font-semibold tabular-nums text-ink">{{ viewYear }} 年 {{ viewMonth + 1 }} 月</span>
            <button
              type="button"
              class="grid h-7 w-7 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
              aria-label="下个月"
              @click="shiftMonth(1)"
            >
              <Icon name="chevron-right" :size="16" />
            </button>
          </div>

          <!-- 星期表头（周一为起点） -->
          <div class="mt-1.5 grid grid-cols-7 text-center text-[10.5px] text-ink-muted">
            <span v-for="w in WEEK" :key="w" class="py-0.5">{{ w }}</span>
          </div>

          <!-- 日期网格：横向零间隙，选中区段连成一条色带 -->
          <div class="grid grid-cols-7 gap-y-0.5" @mouseleave="hoverDate = ''">
            <button
              v-for="c in cells"
              :key="c.key"
              type="button"
              class="h-8 text-[12.5px] tabular-nums transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand/40"
              :class="dayCls(c)"
              :title="c.date === todayKey ? '今天' : c.date"
              :aria-current="c.date === todayKey ? 'date' : undefined"
              :aria-pressed="c.date === draftFrom || c.date === draftTo"
              @click="pick(c)"
              @mouseenter="hoverDate = c.date"
            >
              {{ c.day }}
            </button>
          </div>

          <!-- 常用区间 + 清除（核查近期漏签时最常用的是"近 N 天"） -->
          <div class="mt-2 flex items-center gap-0.5 border-t border-ink/5 pt-2">
            <button
              v-for="p in presets"
              :key="p.label"
              type="button"
              class="rounded-lg px-2 py-1 text-[11.5px] text-ink-muted transition hover:bg-cloud hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
              @click="applyPreset(p)"
            >{{ p.label }}</button>
            <button
              type="button"
              class="ml-auto rounded-lg px-2 py-1 text-[11.5px] font-medium text-ink-muted transition hover:bg-cloud hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
              @click="clear"
            >清除</button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
// 自定义日期选择器（替代浏览器原生 date 输入，样式可控且更紧凑）。
// 两种模式：
//   单选 —— v-model 绑定 'YYYY-MM-DD' | null
//   区间 —— 传 range，用 :from / :to 回显，选满起止后 emit('change', { from, to })
// 日期一律按本地时区取年月日（禁用 toISOString，避免 UTC 差一天）。
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  // 单选模式的值
  modelValue: { type: String, default: null },
  range: { type: Boolean, default: false },
  from: { type: String, default: null },
  to: { type: String, default: null },
  placeholder: { type: String, default: '选择日期' },
  // 表单字段形态：撑满容器 + 输入框外形（弹窗内的独立字段），默认仍是工具栏里的紧凑触发器
  block: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'change'])

const WEEK = ['一', '二', '三', '四', '五', '六', '日']

const open = ref(false)
const root = ref(null)
const trigger = ref(null)
const panel = ref(null)
const panelStyle = ref({ left: '0px', top: '0px' })

// 视图月份（0 基）
const now = new Date()
const viewYear = ref(now.getFullYear())
const viewMonth = ref(now.getMonth())

// 区间选择的草稿与阶段：start=待选起始，end=待选结束
const draftFrom = ref(null)
const draftTo = ref(null)
const phase = ref('start')
const hoverDate = ref('')

const todayKey = localKey(new Date())

// ---- 本地日期工具（不用 toISOString，避免 UTC 偏移跨天） ----
function localKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
function shiftKey(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return localKey(d)
}
function parseKey(key) {
  const [y, m, d] = String(key).split('-').map(Number)
  return { y, m: m - 1, d }
}

// 触发区展示：同年省略年份（完整区间放 title），单边已选时保留一头
const displayText = computed(() => {
  if (!props.range) return props.modelValue || props.placeholder
  const f = props.from
  const t = props.to
  if (!f && !t) return props.placeholder
  if (f && t) return `${fmt(f)} ~ ${fmt(t)}`
  return f ? `${fmt(f)} ~` : `~ ${fmt(t)}`
})
function fmt(key) {
  if (!key) return ''
  const { y, m, d } = parseKey(key)
  const mm = String(m + 1).padStart(2, '0')
  const dd = String(d).padStart(2, '0')
  return y === now.getFullYear() ? `${mm}-${dd}` : `${y}-${mm}-${dd}`
}

const hasValue = computed(() => (props.range ? !!(props.from || props.to) : !!props.modelValue))

// 区间一览时的有效终点：已选终点优先，否则用悬停位置做预览
const effTo = computed(() => draftTo.value || (phase.value === 'end' ? hoverDate.value : ''))

// 42 格（含前后月补位），周一为每周起点
const cells = computed(() => {
  const first = new Date(viewYear.value, viewMonth.value, 1)
  const offset = (first.getDay() + 6) % 7
  const start = new Date(viewYear.value, viewMonth.value, 1 - offset)
  const out = []
  for (let i = 0; i < 42; i++) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
    const date = localKey(d)
    out.push({ key: date, date, day: d.getDate(), inMonth: d.getMonth() === viewMonth.value })
  }
  return out
})

function dayCls(c) {
  const isFrom = c.date === draftFrom.value
  const isTo = c.date === draftTo.value
  if (isFrom || isTo) return 'rounded-lg bg-brand font-semibold text-white'
  const t = effTo.value
  if (draftFrom.value && t && c.date > draftFrom.value && c.date < t) return 'bg-brand/10 text-brand'
  if (!c.inMonth) return 'rounded-lg text-ink/25 hover:bg-cloud'
  if (c.date === todayKey) return 'rounded-lg font-semibold text-brand hover:bg-cloud'
  return 'rounded-lg text-ink-soft hover:bg-cloud'
}

const presets = [
  { label: '近 7 天', from: () => shiftKey(-6), to: () => todayKey },
  { label: '近 30 天', from: () => shiftKey(-29), to: () => todayKey },
  { label: '本月', from: () => localKey(new Date(now.getFullYear(), now.getMonth(), 1)), to: () => todayKey }
]

function toggle() {
  if (props.disabled) return
  open.value ? close() : openPanel()
}

async function openPanel() {
  if (props.disabled || open.value) return
  open.value = true
  if (props.range) {
    draftFrom.value = props.from || null
    draftTo.value = props.to || null
    // 已有完整区间时重开视为「重新选起始」
    phase.value = draftFrom.value && draftTo.value ? 'start' : draftFrom.value ? 'end' : 'start'
  } else {
    draftFrom.value = props.modelValue || null
    draftTo.value = null
  }
  // 视图月份落到已选值或今天所在月
  const anchor = props.range ? props.from || props.to : props.modelValue
  const base = anchor ? parseKey(anchor) : { y: now.getFullYear(), m: now.getMonth() }
  viewYear.value = base.y
  viewMonth.value = base.m
  hoverDate.value = ''
  await nextTick()
  place()
}

function place() {
  const el = trigger.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const pw = 280
  const ph = panel.value ? panel.value.offsetHeight : 300
  const below = window.innerHeight - r.bottom
  const placeTop = below < ph + 12 && r.top > ph + 12
  const left = Math.min(r.left, Math.max(8, window.innerWidth - pw - 8))
  panelStyle.value = {
    left: left + 'px',
    top: (placeTop ? Math.max(8, r.top - ph - 8) : r.bottom + 8) + 'px'
  }
}

function close() {
  open.value = false
}

function shiftMonth(delta) {
  const d = new Date(viewYear.value, viewMonth.value + delta, 1)
  viewYear.value = d.getFullYear()
  viewMonth.value = d.getMonth()
}

// 选中某一天：单选即提交；区间按 start → end 两段，选满即提交并收起
function pick(c) {
  if (!c.inMonth) {
    const d = parseKey(c.date)
    viewYear.value = d.y
    viewMonth.value = d.m
  }
  if (!props.range) {
    emit('update:modelValue', c.date)
    emit('change', { from: c.date, to: c.date })
    close()
    return
  }
  if (phase.value === 'start') {
    draftFrom.value = c.date
    draftTo.value = null
    phase.value = 'end'
    return
  }
  let f = draftFrom.value
  let t = c.date
  if (f && t < f) [f, t] = [t, f]
  draftFrom.value = f
  draftTo.value = t
  phase.value = 'start'
  hoverDate.value = ''
  emit('change', { from: f, to: t })
  close()
}

function applyPreset(p) {
  const f = p.from()
  const t = p.to()
  draftFrom.value = f
  draftTo.value = t
  phase.value = 'start'
  hoverDate.value = ''
  const d = parseKey(f)
  viewYear.value = d.y
  viewMonth.value = d.m
  emit('change', { from: f, to: t })
  close()
}

function clear() {
  draftFrom.value = null
  draftTo.value = null
  phase.value = 'start'
  hoverDate.value = ''
  if (props.range) emit('change', { from: null, to: null })
  else emit('update:modelValue', null)
  close()
}

// ---- 浮层生命周期：外点关闭 / 滚轮与滚动关闭 / 尺寸变化重定位 / Esc 关闭 ----
function onDocClick(e) {
  if (!open.value) return
  if (root.value && root.value.contains(e.target)) return
  if (panel.value && panel.value.contains(e.target)) return
  close()
}
function onScrollClose(e) {
  if (panel.value && panel.value.contains(e.target)) return
  close()
}
function onResize() {
  if (open.value) place()
}
function onKeydown(e) {
  if (e.key === 'Escape') close()
}

watch(open, (v) => {
  if (v) {
    document.addEventListener('mousedown', onDocClick)
    window.addEventListener('resize', onResize)
    window.addEventListener('scroll', onScrollClose, true)
    window.addEventListener('keydown', onKeydown)
  } else {
    document.removeEventListener('mousedown', onDocClick)
    window.removeEventListener('resize', onResize)
    window.removeEventListener('scroll', onScrollClose, true)
    window.removeEventListener('keydown', onKeydown)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocClick)
  window.removeEventListener('resize', onResize)
  window.removeEventListener('scroll', onScrollClose, true)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.xb-pop-enter-active,
.xb-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.xb-pop-enter-from,
.xb-pop-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
@media (prefers-reduced-motion: reduce) {
  .xb-pop-enter-active,
  .xb-pop-leave-active {
    transition: none;
  }
}
</style>
