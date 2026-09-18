<template>
  <!-- 图库选择器：在选项文字前内嵌 3 张缩略图，让「选哪个库」变成看得见的选择。
       tone="fallback" 用于兜底行：虚线描边 + 浅底，与常规选择在视觉上区分开。 -->
  <BaseSelect
    :model-value="modelValue"
    :options="options"
    :placeholder="placeholder"
    :disabled="disabled"
    :searchable="true"
    size="sm"
    :class="tone === 'fallback' ? 'xb-picker-fallback' : ''"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <template #prefix>
      <span class="flex flex-none gap-[3px]" aria-hidden="true">
        <template v-for="s in slots" :key="s.key">
          <img v-if="s.url" :src="s.url" alt="" class="h-5 w-5 flex-none rounded-md object-cover" />
          <span v-else class="h-5 w-5 flex-none rounded-md bg-cloud" />
        </template>
      </span>
    </template>
  </BaseSelect>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import BaseSelect from '@/components/BaseSelect.vue'
import { fetchImageBlobUrl } from '@/api/signConfig'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, default: () => [] },
  // 当前范围内的候选图片，取前 3 张做预览（父层已按图库范围与策略过滤好）
  images: { type: Array, default: () => [] },
  placeholder: { type: String, default: '全部图库' },
  disabled: { type: Boolean, default: false },
  tone: { type: String, default: 'default' } // default | fallback
})

defineEmits(['update:modelValue'])

// 缩略图恒占 3 格：图库空时留灰块，比整条消失更能说明「这个库没图」
const THUMB_COUNT = 3
const urls = ref({})
const slots = computed(() => {
  const out = props.images.slice(0, THUMB_COUNT).map((img) => ({
    key: String(img.id),
    url: urls.value[img.id] || ''
  }))
  while (out.length < THUMB_COUNT) out.push({ key: 'pad-' + out.length, url: '' })
  return out
})

// 缩略图走 blob 拉取（<img> 带不上 Authorization 头），api 层有会话级缓存，重复预览不重复请求。
// 序号守卫：快速切换图库时丢弃过期响应，避免旧图盖住新图。
let thumbToken = 0
async function loadThumbs() {
  const token = ++thumbToken
  const ids = props.images.slice(0, THUMB_COUNT).map((img) => img.id)
  const pairs = await Promise.all(
    ids.map(async (id) => [id, await fetchImageBlobUrl(id).catch(() => '')])
  )
  if (token !== thumbToken) return
  const next = {}
  for (const [id, url] of pairs) if (url) next[id] = url
  urls.value = next
}

onMounted(loadThumbs)

// 与 script setup 末尾约定一致：watch 写在最后，避免 setup 阶段 TDZ
watch(() => props.images.map((img) => img.id).join(','), loadThumbs)
</script>

<style scoped>
.xb-picker-fallback :deep(.xb-select-trigger) {
  border-style: dashed;
  background: rgb(var(--colors-cloud) / 0.6);
}
</style>
