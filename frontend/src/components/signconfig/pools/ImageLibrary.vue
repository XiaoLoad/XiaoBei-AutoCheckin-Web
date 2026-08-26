<template>
  <div class="space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="inline-flex rounded-xl bg-cloud p-1 text-sm">
        <button
          v-for="v in views"
          :key="v.value"
          type="button"
          class="rounded-lg px-3 py-1.5 font-medium transition"
          :class="view === v.value ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
          @click="view = v.value"
        >
          {{ v.label }}
        </button>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-60"
        :disabled="uploading"
        @click="fileInput?.click()"
      >
        <span v-if="uploading" class="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
        <Icon v-else name="plus" :size="15" />{{ uploading ? '上传中…' : '上传图片' }}
      </button>
    </div>

    <input ref="fileInput" type="file" accept="image/jpeg,image/png" multiple class="hidden" @change="onFilesPicked" />

    <div v-if="list.length === 0" class="py-8 text-center text-sm text-ink-muted">暂无图片</div>
    <div v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      <div v-for="img in list" :key="img.id" class="overflow-hidden rounded-xl border border-ink/10 bg-white">
        <div class="grid h-24 place-items-center overflow-hidden bg-gradient-to-br from-cloud to-brand/10">
          <img v-if="urls[img.id]" :src="urls[img.id]" class="h-full w-full object-cover" alt="" />
          <Icon v-else name="image" :size="26" class="text-ink-muted" />
        </div>
        <div class="flex items-center justify-between gap-1 px-2 py-1.5">
          <p class="min-w-0 flex-1 truncate text-xs text-ink-soft">{{ img.name }}</p>
          <span class="shrink-0 text-[11px] text-ink-muted">{{ img.sizeKb }}KB</span>
        </div>
        <div class="flex justify-end gap-2 border-t border-ink/5 px-2 py-1.5">
          <button v-if="!img.inTrash" class="text-[11px] text-ink-muted hover:text-danger" @click="toTrash(img.id)">移入回收站</button>
          <button v-else class="text-[11px] text-info hover:underline" @click="restore(img.id)">恢复</button>
          <button class="text-[11px] text-danger hover:underline" @click="remove(img.id)">删除</button>
        </div>
      </div>
    </div>

    <p class="text-xs text-ink-muted">上传即自动压缩至 ≤180KB、长边 ≤1920px（B 平台提交口径）；回收站保留 7 天后自动清除。</p>
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch } from 'vue'
import Icon from '@/components/Icon.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { fetchImageBlobUrl } from '@/api/signConfig'
import toast from '@/utils/toast'

const store = useSignConfigStore()
const view = ref('active')
const views = [
  { value: 'active', label: '图库' },
  { value: 'trash', label: '回收站' }
]
const list = computed(() => store.imageLibrary.filter((i) => (view.value === 'trash' ? i.inTrash : !i.inTrash)))

// ── 真实上传 ──
const fileInput = ref(null)
const uploading = ref(false)

async function onFilesPicked(e) {
  const files = Array.from(e.target.files || [])
  e.target.value = ''
  if (!files.length) return
  uploading.value = true
  let okCount = 0
  try {
    for (const f of files) {
      try {
        await store.uploadImage(f)
        okCount += 1
      } catch (err) {
        toast(`「${f.name}」上传失败：${err.message || '未知错误'}`, 'error')
      }
    }
    if (okCount) toast(`已上传 ${okCount} 张图片`, 'success')
  } finally {
    uploading.value = false
  }
}

// ── 缩略图：blob objectURL 会话级缓存 ──
const urls = reactive({})

watch(list, async (rows) => {
  for (const r of rows) {
    if (!urls[r.id]) {
      try { urls[r.id] = await fetchImageBlobUrl(r.id) } catch { /* 文件丢失时留图标占位 */ }
    }
  }
}, { immediate: true })

function toTrash(id) { store.trashImage(id) }
function restore(id) { store.restoreImage(id) }
function remove(id) { store.deleteImage(id) }
</script>
