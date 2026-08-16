<template>
  <ConfigSection title="备注列表" icon="file" :source="source" :error="error" :required="required">
    <p class="mb-2 text-xs text-ink-muted">签到时后台随机选取一条提交；可按 B 平台账号设置带名备注（如"xxx签到"）。</p>

    <p v-if="config.remarks.length === 0" class="rounded-xl border border-dashed border-ink/15 px-3 py-3 text-center text-xs text-ink-muted">
      暂无备注，点击下方「添加备注」新增一条
    </p>

    <transition-group name="remark" tag="div" class="relative space-y-2">
      <div v-for="(r, i) in config.remarks" :key="keys[i]" class="flex items-center gap-2">
        <input
          :ref="(el) => setInputRef(el, i)"
          v-model="config.remarks[i]"
          class="flex-1 rounded-xl border bg-white px-3 py-2 text-sm text-ink outline-none transition"
          :class="hintIndex === i ? 'border-danger ring-4 ring-danger/10' : 'border-ink/10 focus:border-brand focus:ring-4 focus:ring-brand/10'"
          placeholder="输入备注内容"
          @blur="onRemarkBlur(i)"
        />
        <button
          type="button"
          class="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-ink/10 text-ink-muted transition hover:bg-danger/10 hover:text-danger"
          aria-label="删除备注"
          @mousedown.prevent
          @click="removeRemark(i)"
        >
          <Icon name="trash" :size="15" />
        </button>
      </div>
    </transition-group>

    <div class="mt-2 flex flex-wrap items-center gap-2">
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-ink/20 px-3 py-2 text-sm text-ink-soft transition hover:bg-cloud"
        @mousedown.prevent
        @click="addRemark"
      >
        <Icon name="plus" :size="15" />添加备注
      </button>
      <span v-if="hintIndex !== -1" class="text-xs text-danger">请先填写当前这条备注</span>
    </div>
  </ConfigSection>
</template>

<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' },
  error: { type: String, default: '' },
  required: { type: Boolean, default: false }
})

// 备注本身是字符串数组（后端契约），另用一份并行 key 保证列表项在增删时身份稳定，
// 避免用索引作 key 导致过渡动画与输入框复用错位。
let seed = 0
const keys = ref([])
const inputEls = ref([])
const hintIndex = ref(-1)
let hintTimer = null

function nextKey() {
  return `r${seed++}`
}
function rebuildKeys() {
  keys.value = props.config.remarks.map(nextKey)
}
// 切换配置套 / 任务实例时 config 整体替换，重建 key；外部直接改数组长度时兜底补齐
watch(() => props.config.remarks, rebuildKeys, { immediate: true })
watch(
  () => props.config.remarks.length,
  (len) => {
    while (keys.value.length < len) keys.value.push(nextKey())
    if (keys.value.length > len) keys.value.splice(len)
  }
)

function setInputRef(el, i) {
  if (el) inputEls.value[i] = el
}

function showHint(i) {
  hintIndex.value = i
  if (hintTimer) clearTimeout(hintTimer)
  hintTimer = setTimeout(() => (hintIndex.value = -1), 1600)
}

// 列表为空时直接新增；末尾已有空行则不再叠加，改为聚焦并提示，避免点击"没反应"
async function addRemark() {
  const list = props.config.remarks
  const last = list.length - 1
  if (last >= 0 && String(list[last] ?? '').trim() === '') {
    showHint(last)
    await nextTick()
    if (inputEls.value[last]) inputEls.value[last].focus()
    return
  }
  list.push('')
  keys.value.push(nextKey())
  await nextTick()
  const idx = list.length - 1
  if (inputEls.value[idx]) inputEls.value[idx].focus()
}

function removeRemark(i) {
  props.config.remarks.splice(i, 1)
  keys.value.splice(i, 1)
  inputEls.value.splice(i, 1)
  if (hintIndex.value === i) hintIndex.value = -1
}

// 失焦时若内容为空则移除该输入框（含仅剩一条也为空的情形），避免留出空行
function onRemarkBlur(i) {
  const list = props.config.remarks
  if (i < 0 || i >= list.length) return
  if (String(list[i] ?? '').trim() === '') removeRemark(i)
}

onBeforeUnmount(() => {
  if (hintTimer) clearTimeout(hintTimer)
})
</script>
