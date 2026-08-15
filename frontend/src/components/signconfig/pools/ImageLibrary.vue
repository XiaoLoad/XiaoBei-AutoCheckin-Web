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
        class="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-dark"
        @click="uploadMock"
      >
        <Icon name="plus" :size="15" />上传图片
      </button>
    </div>

    <div class="rounded-xl border border-dashed border-ink/15 bg-cloud/40 px-4 py-6 text-center text-xs text-ink-muted">
      框架阶段：拖拽 / 批量上传与自动压缩至 200KB 将在后端接入后落地；此处的「上传图片」仅向图库追加一条演示记录。
    </div>

    <div v-if="list.length === 0" class="py-8 text-center text-sm text-ink-muted">暂无图片</div>
    <div v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      <div v-for="img in list" :key="img.id" class="overflow-hidden rounded-xl border border-ink/10 bg-white">
        <div class="grid h-24 place-items-center bg-gradient-to-br from-cloud to-brand/10 text-ink-muted">
          <Icon name="image" :size="26" />
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

    <p class="text-xs text-ink-muted">分页管理与放大查看将在后端资源接口就绪后补充。</p>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import Icon from '@/components/Icon.vue'
import { useSignConfigStore } from '@/stores/signConfig'

const store = useSignConfigStore()
const view = ref('active')
const views = [
  { value: 'active', label: '图库' },
  { value: 'trash', label: '回收站' }
]
const list = computed(() => store.imageLibrary.filter((i) => (view.value === 'trash' ? i.inTrash : !i.inTrash)))

function uploadMock() {
  store.saveImage({ name: `新图片_${Math.floor(Math.random() * 900 + 100)}.jpg`, sizeKb: 120 + Math.floor(Math.random() * 60) })
}
function toTrash(id) {
  store.trashImage(id)
}
function restore(id) {
  store.restoreImage(id)
}
function remove(id) {
  store.deleteImage(id)
}
</script>
