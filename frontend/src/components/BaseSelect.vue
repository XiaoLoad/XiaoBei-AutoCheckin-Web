<template>
  <div ref="root" class="xb-select relative inline-block w-full" :class="{ 'pointer-events-none opacity-60': disabled }">
    <!-- 触发器：替换原生 select，外观沿用 login-input -->
    <button
      type="button"
      class="xb-select-trigger flex w-full items-center justify-between gap-2 rounded-xl border border-ink/10 bg-white text-left text-sm text-ink-soft outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
      :class="size === 'sm' ? 'py-2 px-2.5' : 'py-2.5 px-3'"
      :disabled="disabled"
      @click="toggle"
      @keydown="onKeydown"
    >
      <span class="min-w-0 flex-1 truncate" :class="selectedLabel ? 'text-ink' : 'text-ink-muted'">
        {{ selectedLabel || placeholder }}
      </span>
      <Icon name="chevron-down" :size="16" class="shrink-0 text-ink-muted transition-transform duration-200" :class="open && 'rotate-180'" />
    </button>

    <!-- 下拉面板：Teleport 到 body，脱离滚动容器，避免展开时撑开页面引发抖动 -->
    <Teleport to="body">
      <transition name="xb-pop">
        <div
          v-if="open"
          ref="panel"
          class="xb-select-panel fixed z-[1000] overflow-hidden rounded-xl border border-ink/10 bg-white shadow-xl shadow-ink/10"
          :style="panelStyle"
          :class="panelPlacement === 'top' ? 'origin-bottom' : 'origin-top'"
        >
          <!-- 模糊搜索（searchable 版本） -->
          <div v-if="searchable" class="border-b border-ink/5 p-2">
            <div class="relative">
              <Icon name="search" :size="15" class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted" />
              <input
                ref="searchInput"
                v-model="query"
                type="text"
                placeholder="搜索…"
                class="w-full rounded-lg border border-ink/10 bg-cloud/40 py-1.5 pl-8 pr-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/10"
                @keydown.stop="onSearchKeydown"
              />
            </div>
          </div>

          <ul ref="list" class="xb-select-list max-h-60 overflow-auto py-1">
            <li
              v-for="(opt, i) in filteredOptions"
              :key="String(opt.value)"
              class="xb-select-option flex cursor-pointer items-center justify-between gap-2 px-3 py-1.5 text-sm transition"
              :class="[
                i === highlightedIndex ? 'bg-cloud' : '',
                isSelected(opt) ? 'font-medium text-brand' : 'text-ink-soft'
              ]"
              @mouseenter="highlightedIndex = i"
              @click="select(opt)"
            >
              <span class="min-w-0 flex-1 truncate">{{ opt.label }}</span>
              <Icon v-if="isSelected(opt)" name="check" :size="15" class="shrink-0 text-brand" />
            </li>
            <li v-if="filteredOptions.length === 0" class="px-3 py-3 text-center text-sm text-ink-muted">
              无匹配项
            </li>
          </ul>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  modelValue: { type: [String, Number, Boolean], default: '' },
  // 通用数据：可为 字符串/数字 数组，或 { label, value } 对象数组
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '请选择' },
  // 两版本开关：false=普通下拉；true=带模糊搜索（选项较多时使用）
  searchable: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  size: { type: String, default: 'md' }, // md | sm
  // 展开方向：bottom 向下 / top 向上 / auto 按可用空间自适应（默认 bottom，保持旧行为）
  placement: { type: String, default: 'bottom' }
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const query = ref('')
const highlightedIndex = ref(-1)
const root = ref(null)
const list = ref(null)
const searchInput = ref(null)
const panel = ref(null)
const panelPlacement = ref(props.placement === 'auto' ? 'bottom' : props.placement)
// 面板位置（fixed，相对视口）：由触发器 getBoundingClientRect 计算，脱离滚动容器
const panelStyle = ref({ left: '0px', top: '0px', width: '0px' })

// 归一化选项为 { label, value }
const normalized = computed(() =>
  props.options.map((o) =>
    typeof o === 'object' && o !== null
      ? { label: String(o.label), value: o.value }
      : { label: String(o), value: o }
  )
)

const selectedLabel = computed(() => {
  const hit = normalized.value.find((o) => o.value === props.modelValue)
  return hit ? hit.label : ''
})

const filteredOptions = computed(() => {
  if (!props.searchable || !query.value.trim()) return normalized.value
  const kw = query.value.trim().toLowerCase()
  return normalized.value.filter((o) => o.label.toLowerCase().includes(kw))
})

function isSelected(opt) {
  return opt.value === props.modelValue
}

function toggle() {
  if (props.disabled) return
  if (open.value) close()
  else openPanel()
}

async function openPanel() {
  if (props.disabled || open.value) return
  open.value = true
  query.value = ''
  const idx = normalized.value.findIndex((o) => o.value === props.modelValue)
  highlightedIndex.value = idx >= 0 ? idx : 0
  await nextTick()
  refinePlacement()
  if (props.searchable && searchInput.value) searchInput.value.focus()
}

// 面板定位：始终以视口坐标（fixed）渲染在 body 下，按可用空间自动上/下翻转。
// 面板挂 body 而非滚动容器内，展开后不会撑大页面滚动高度，从而避免抖动。
function refinePlacement() {
  const trigger = root.value
  if (!trigger) return
  const rect = trigger.getBoundingClientRect()
  const ph = panel.value ? panel.value.offsetHeight : 240
  const spaceBelow = window.innerHeight - rect.bottom
  const spaceAbove = rect.top
  const placeTop = spaceBelow < ph + 12 && spaceAbove > ph + 12
  panelPlacement.value = placeTop ? 'top' : 'bottom'
  const width = trigger.offsetWidth
  // 面板至少与触发器同宽（避免比输入框还窄），但按内容自适应撑宽以完整显示选项文字，
  // 并用 90vw 封顶，防止超长选项把面板拉出视口。
  const style = { left: rect.left + 'px', minWidth: width + 'px', maxWidth: '90vw' }
  if (placeTop) style.top = Math.max(8, rect.top - ph - 8) + 'px'
  else style.top = rect.bottom + 8 + 'px'
  panelStyle.value = style
}

function onResize() {
  if (open.value) refinePlacement()
}

// 展开时监听滚动：页面滚动则关闭面板（忽略面板内部列表自身的滚动），
// 避免面板脱离触发器悬空；同时用户滚动通常意味着放弃当前选择。
function onScrollClose(e) {
  if (panel.value && panel.value.contains(e.target)) return
  close()
}

function select(opt) {
  open.value = false
  query.value = ''
  emit('update:modelValue', opt.value)
}

function close() {
  open.value = false
  query.value = ''
}

function scrollActiveIntoView() {
  nextTick(() => {
    const el = list.value && list.value.children[highlightedIndex.value]
    if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' })
  })
}

function move(delta) {
  const len = filteredOptions.value.length
  if (len === 0) return
  let i = highlightedIndex.value
  i = (i + delta + len) % len
  highlightedIndex.value = i
  scrollActiveIntoView()
}

// 触发器键盘：上下打开并移动，回车/空格选择，Esc 关闭
function onKeydown(e) {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault()
    if (!open.value) toggle()
    else move(e.key === 'ArrowDown' ? 1 : -1)
  } else if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    if (!open.value) toggle()
    else if (filteredOptions.value[highlightedIndex.value]) select(filteredOptions.value[highlightedIndex.value])
  } else if (e.key === 'Escape') {
    close()
  }
}

// 搜索框键盘：上下移动、回车选择、Esc 关闭面板
function onSearchKeydown(e) {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    move(1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    move(-1)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    if (filteredOptions.value[highlightedIndex.value]) select(filteredOptions.value[highlightedIndex.value])
  } else if (e.key === 'Escape') {
    e.stopPropagation()
    close()
  }
}

// 点击外部关闭
function onDocClick(e) {
  if (open.value && root.value && !root.value.contains(e.target)) close()
}

watch(open, (v) => {
  if (v) {
    document.addEventListener('mousedown', onDocClick)
    window.addEventListener('resize', onResize)
    // capture 阶段监听，可捕获任意容器（含滚动主区域）的滚动；面板内列表滚动已单独排除
    window.addEventListener('scroll', onScrollClose, true)
  } else {
    document.removeEventListener('mousedown', onDocClick)
    window.removeEventListener('resize', onResize)
    window.removeEventListener('scroll', onScrollClose, true)
  }
})

onMounted(() => document.removeEventListener('mousedown', onDocClick))
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocClick)
  window.removeEventListener('resize', onResize)
  window.removeEventListener('scroll', onScrollClose, true)
})
</script>

<style scoped>
.xb-pop-enter-active,
.xb-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
/* 向下展开（top 定位）从上方滑入；向上展开（bottom 定位）从下方滑入，避免与触发器方向冲突 */
.xb-pop-enter-from.xb-select-panel,
.xb-pop-leave-to.xb-select-panel {
  opacity: 0;
}
.xb-pop-enter-from.origin-top,
.xb-pop-leave-to.origin-top {
  transform: translateY(-4px);
}
.xb-pop-enter-from.origin-bottom,
.xb-pop-leave-to.origin-bottom {
  transform: translateY(4px);
}
</style>
