<template>
  <div ref="root" class="xb-select relative inline-block w-full" :class="{ 'pointer-events-none opacity-60': disabled }">
    <!-- 可输入（combobox）模式：触发器为输入框，既可下拉选择也可直接键入筛选/取值 -->
    <div
      v-if="editable"
      class="xb-select-trigger flex w-full items-center justify-between gap-2 rounded-xl border border-ink/10 bg-elevated text-left text-sm text-ink outline-none transition focus-within:border-brand focus-within:ring-4 focus-within:ring-brand/10"
      :class="size === 'sm' ? 'py-1.5 px-2.5' : 'py-2 px-3'"
    >
      <input
        ref="triggerInput"
        type="text"
        :inputmode="numeric ? 'numeric' : 'text'"
        :value="draft"
        :placeholder="placeholder"
        role="combobox"
        aria-haspopup="listbox"
        :aria-expanded="open"
        aria-autocomplete="list"
        :aria-activedescendant="open && highlightedIndex >= 0 ? listboxId + '-' + highlightedIndex : undefined"
        :aria-controls="open ? listboxId : undefined"
        class="min-w-0 flex-1 bg-transparent text-ink outline-none placeholder:text-ink-muted"
        :disabled="disabled"
        @focus="onEditableFocus"
        @input="onEditableInput"
        @keydown="onEditableKeydown"
        @blur="onEditableBlur"
      />
      <Icon
        name="chevron-down"
        :size="16"
        class="shrink-0 text-ink-muted transition-transform duration-200"
        :class="open && 'rotate-180'"
        @click.stop="toggle"
      />
    </div>

    <!-- 纯下拉模式（默认）：触发器为按钮 -->
    <button
      v-else
      type="button"
      class="xb-select-trigger flex w-full items-center justify-between gap-2 rounded-xl border border-ink/10 bg-elevated text-left text-sm text-ink-soft outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
      :class="size === 'sm' ? 'py-2 px-2.5' : 'py-2.5 px-3'"
      aria-haspopup="listbox"
      :aria-expanded="open"
      :aria-activedescendant="open && highlightedIndex >= 0 ? listboxId + '-' + highlightedIndex : undefined"
      :aria-controls="open ? listboxId : undefined"
      :disabled="disabled"
      @click="toggle"
      @keydown="onKeydown"
    >
      <!-- 触发区前置槽：调用方可在选项文字前放缩略图等标记（不传时外观与原来完全一致） -->
      <slot name="prefix" />
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
          class="xb-select-panel fixed z-[1000] overflow-hidden rounded-xl border border-ink/10 bg-elevated shadow-xl shadow-ink/10"
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
                aria-label="搜索选项"
                class="w-full rounded-lg border border-ink/10 bg-cloud/40 py-1.5 pl-8 pr-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/10"
                @keydown.stop="onSearchKeydown"
              />
            </div>
          </div>

          <ul :id="listboxId" ref="list" role="listbox" class="xb-select-list max-h-60 overflow-auto py-1">
            <li
              v-for="(opt, i) in filteredOptions"
              :key="String(opt.value)"
              :id="listboxId + '-' + i"
              role="option"
              :aria-selected="isSelected(opt)"
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
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
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
  placement: { type: String, default: 'bottom' },
  // 可输入模式：触发器改为输入框，支持键入筛选/取值（下拉仍可用）；默认关闭，不影响既有纯下拉用法
  editable: { type: Boolean, default: false },
  // 可输入模式下键盘为数字键盘（时间等纯数字场景）
  numeric: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue'])

// 组件实例 id 种子（模块级）：为 listbox/option 生成全页唯一 id
let listboxSeed = 0

const open = ref(false)
const query = ref('')
// listbox 稳定 id：供 aria-activedescendant 指向当前高亮项（多实例共存不冲突）
const listboxId = `xb-listbox-${++listboxSeed}`
const highlightedIndex = ref(-1)
const root = ref(null)
const list = ref(null)
const searchInput = ref(null)
const triggerInput = ref(null)
const panel = ref(null)
const panelPlacement = ref(props.placement === 'auto' ? 'bottom' : props.placement)
// 面板位置（fixed，相对视口）：由触发器 getBoundingClientRect 计算，脱离滚动容器
const panelStyle = ref({ left: '0px', top: '0px', width: '0px' })
// 程序化滚动（聚焦输入框时浏览器把触发器滚入视口）期间临时屏蔽「滚动即关闭」，
// 避免面板被 focus/select 触发的滚动误关；坐标稳定后再重算位置。
const suppressScrollClose = ref(false)

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
// 可输入模式：草稿文本（未聚焦时与所选 label 同步，聚焦时可键入筛选/取值）
const draft = ref(selectedLabel.value)
// 用户本次聚焦后是否已键入：openPanel 的异步全选仅在未键入时执行，
// 避免聚焦后快速打字被迟到的 select() 全选覆盖（首个字符被"闪回"丢失）
const draftDirty = ref(false)

const filteredOptions = computed(() => {
  if (!props.searchable && !props.editable) return normalized.value
  const kw = query.value.trim().toLowerCase()
  if (!kw) return normalized.value
  return normalized.value.filter(
    (o) => o.label.toLowerCase().includes(kw) || String(o.value).toLowerCase().includes(kw)
  )
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
  // 展开时同步草稿为所选 label；但"键入重开"路径（draftDirty=true）保留用户已键入文本
  if (props.editable && !draftDirty.value) draft.value = selectedLabel.value
  const idx = normalized.value.findIndex((o) => o.value === props.modelValue)
  highlightedIndex.value = idx >= 0 ? idx : 0
  await nextTick()
  refinePlacement()
  if (props.searchable && searchInput.value) searchInput.value.focus()
  if (props.editable && triggerInput.value) {
    // 先聚焦并全选：浏览器可能把触发器滚入视口（改变其视口坐标），期间屏蔽滚动误关；
    // 待坐标稳定后基于最终矩形重算面板位置，避免面板悬空在上或错位。
    suppressScrollClose.value = true
    triggerInput.value.focus()
    if (!draftDirty.value) triggerInput.value.select()
    await nextTick()
    refinePlacement()
    requestAnimationFrame(() => { suppressScrollClose.value = false })
  }
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
  if (suppressScrollClose.value) return
  if (panel.value && panel.value.contains(e.target)) return
  close()
}

function select(opt) {
  open.value = false
  query.value = ''
  draftDirty.value = false
  if (props.editable) draft.value = opt.label
  emit('update:modelValue', opt.value)
}

// 关闭面板不再回退草稿：可输入模式下草稿的定稿/回退由 blur 的 commitDraft 与
// Esc 显式处理——此前在外部 mousedown（close 先于 blur 执行）抢先回退，导致
// 键入的值必须点击选项或回车才能生效（点击外部即丢失，表现为数字闪回旧值）
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

// 可输入/搜索模式下筛选结果变化后，面板内容高度改变，需重算定位
// （否则向上展开时 top 仍按旧高度计算，短结果会悬空在输入框上方）。
watch(filteredOptions, () => {
  if (open.value && (props.editable || props.searchable)) nextTick(refinePlacement)
})

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

// —— 可输入（combobox）模式的交互 ——
// 选中项变化时（关闭态）同步草稿文本，保证输入框展示当前所选 label（如补零的「07」）
watch(selectedLabel, (v) => {
  if (!open.value) draft.value = v
})

function onEditableFocus() {
  if (props.disabled) return
  draftDirty.value = false // 全新编辑会话：openPanel 可安全同步 label 并全选
  openPanel()
}

function onEditableInput(e) {
  draft.value = e.target.value
  draftDirty.value = true
  query.value = e.target.value
  // 面板意外关闭（如滚动）后继续键入时重新展开，保持"输入即筛选"的连续体验
  if (!open.value) openPanel()
}

// 把键入文本解析为选项值：优先精确 label 匹配，其次按数字值匹配（时间补零场景），
// 再退化为唯一筛选结果；均不匹配则回退到当前选择，避免误写非法值。
function commitDraft() {
  const t = (draft.value || '').trim()
  if (!t) {
    draft.value = selectedLabel.value
    close()
    return
  }
  const byLabel = normalized.value.find((o) => o.label.toLowerCase() === t.toLowerCase())
  if (byLabel) {
    select(byLabel)
    return
  }
  const num = Number(t)
  if (t !== '' && !Number.isNaN(num)) {
    const byVal = normalized.value.find((o) => o.value === num || o.value === t)
    if (byVal) {
      select(byVal)
      return
    }
  }
  const f = filteredOptions.value
  if (f.length === 1) {
    select(f[0])
    return
  }
  draft.value = selectedLabel.value
  close()
}

function onEditableKeydown(e) {
  if (e.key === 'Enter') {
    e.preventDefault()
    commitDraft()
  } else if (e.key === 'Escape') {
    e.preventDefault()
    draft.value = selectedLabel.value
    close()
  } else if (e.key === 'ArrowDown') {
    e.preventDefault()
    if (!open.value) openPanel()
    else move(1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    if (!open.value) openPanel()
    else move(-1)
  }
}

// 失焦时按键入内容定稿（选不到合法值则回退当前选择）；点击面板内选项时由选项 @click 覆盖。
function onEditableBlur() {
  commitDraft()
  draftDirty.value = false
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

// 点击外部关闭。⚠️面板被 Teleport 到 body、不在 root 之内，必须单独判一次：
// 否则点选项时 mousedown 就先判成「点了外部」把面板关掉，面板开始退场淡出、选项的 click
// 再落到已消失的元素上——现象就是「点下拉闪一下」，慢一点还会丢选择。
function onDocClick(e) {
  if (!open.value) return
  if (root.value && root.value.contains(e.target)) return
  if (panel.value && panel.value.contains(e.target)) return
  close()
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
