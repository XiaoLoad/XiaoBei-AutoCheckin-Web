<template>
  <div class="flex min-h-0 gap-3">
    <!-- 左：分组侧栏（相册式管理 + 拖拽投放目标） -->
    <aside class="flex max-h-[72vh] w-52 shrink-0 flex-col overflow-hidden rounded-2xl dash-card">
      <div class="border-b border-ink/5 p-2">
        <div class="relative">
          <Icon name="search" :size="13" class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input
            v-model="groupQuery"
            type="text"
            placeholder="搜索分组…"
            class="w-full rounded-lg border border-ink/10 bg-cloud/40 py-1.5 pl-7 pr-2 text-xs text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/10"
          />
        </div>
      </div>
      <div class="xb-scroll flex-1 min-h-0 overflow-auto p-1.5">
        <!-- 全部（非投放目标） -->
        <div
          class="flex cursor-pointer items-center gap-1 rounded-lg px-2 py-1.5 text-sm transition"
          :class="groupFilter === 'all' ? 'bg-brand/10 font-medium text-brand' : 'text-ink-soft hover:bg-cloud'"
          @click="groupFilter = 'all'"
        >
          <span class="min-w-0 flex-1 truncate">全部</span>
          <span class="shrink-0 text-[11px] text-ink-muted">{{ counts.all }}</span>
        </div>
        <!-- 未分组（可投放） -->
        <div
          v-show="matchesGroupQuery('未分组')"
          class="flex cursor-pointer items-center gap-1 rounded-lg px-2 py-1.5 text-sm transition"
          :class="[
            groupFilter === 'ungrouped' ? 'bg-brand/10 font-medium text-brand' : 'text-ink-soft hover:bg-cloud',
            dropKey === 'ungrouped' ? 'ring-2 ring-brand' : ''
          ]"
          @click="groupFilter = 'ungrouped'"
          @dragover.prevent="dropKey = 'ungrouped'"
          @dragleave="dropKey === 'ungrouped' && (dropKey = null)"
          @drop.prevent="onDropTo('ungrouped')"
        >
          <span class="min-w-0 flex-1 truncate">未分组</span>
          <span class="shrink-0 text-[11px] text-ink-muted">{{ counts.ungrouped }}</span>
        </div>
        <!-- 用户自建分组（可投放；hover 显示重命名/删除） -->
        <div
          v-for="g in visibleGroups"
          :key="g.id"
          class="group/row flex cursor-pointer items-center gap-1 rounded-lg px-2 py-1.5 text-sm transition"
          :class="[
            groupFilter === g.id ? 'bg-brand/10 font-medium text-brand' : 'text-ink-soft hover:bg-cloud',
            dropKey === g.id ? 'ring-2 ring-brand' : ''
          ]"
          @click="editingGroupId === g.id ? null : (groupFilter = g.id)"
          @dragover.prevent="dropKey = g.id"
          @dragleave="dropKey === g.id && (dropKey = null)"
          @drop.prevent="onDropTo(g.id)"
        >
          <template v-if="editingGroupId === g.id">
            <input
              v-model="editingName"
              type="text"
              class="min-w-0 flex-1 rounded-lg border border-ink/10 bg-white px-2 py-1.5 text-xs text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/10"
              @keyup.enter="confirmRename"
              @click.stop
            />
            <button
              type="button"
              class="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-brand transition hover:bg-brand/10"
              aria-label="保存"
              @click.stop="confirmRename"
            >
              <Icon name="check" :size="14" />
            </button>
            <button
              type="button"
              class="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud"
              aria-label="取消"
              @click.stop="editingGroupId = null"
            >
              <Icon name="close" :size="14" />
            </button>
          </template>
          <template v-else>
            <span class="min-w-0 flex-1 truncate" :title="g.name">{{ g.name }}</span>
            <span class="shrink-0 text-[11px] text-ink-muted">{{ counts[g.id] ?? 0 }}</span>
            <span class="hidden shrink-0 items-center gap-0.5 group-hover/row:flex">
              <Icon name="edit" :size="12" class="cursor-pointer text-ink-muted hover:text-brand" @click.stop="startRename(g)" />
              <Icon name="trash" :size="12" class="cursor-pointer text-ink-muted hover:text-danger" @click.stop="removeGroup(g)" />
            </span>
          </template>
        </div>
        <!-- 新建分组 -->
        <div v-if="creating" class="space-y-1.5 rounded-lg bg-brand/5 p-2">
          <input
            v-model="newName"
            type="text"
            placeholder="分组名，如 3栋507"
            class="w-full rounded-lg border border-ink/10 bg-white px-2.5 py-2 text-xs text-ink outline-none transition placeholder:text-ink-muted focus:border-brand focus:ring-2 focus:ring-brand/10"
            @keyup.enter="confirmCreate"
            @keyup.esc="creating = false"
          />
          <div class="flex items-center gap-1.5">
            <button
              type="button"
              class="flex-1 rounded-lg bg-brand px-3 py-2 text-xs font-medium text-white transition hover:bg-brand-dark active:scale-[0.98]"
              @click="confirmCreate"
            >保存</button>
            <button
              type="button"
              class="flex-1 rounded-lg border border-ink/15 bg-white px-3 py-2 text-xs font-medium text-ink-soft transition hover:bg-cloud active:scale-[0.98]"
              @click="creating = false"
            >取消</button>
          </div>
        </div>
        <button
          v-else
          type="button"
          class="mt-0.5 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-ink/20 px-2 py-2 text-xs text-ink-soft transition hover:border-brand hover:text-brand"
          @click="creating = true"
        >
          <Icon name="plus" :size="13" />新建分组
        </button>
        <p v-if="groupsEmpty && groupQuery" class="px-2 py-1.5 text-center text-[11px] text-ink-muted">无匹配分组</p>
      </div>
      <p class="border-t border-ink/5 px-3 py-2 text-[11px] leading-relaxed text-ink-muted">
        同寝室账号共用同一分组；不同寝室各建各的组。
      </p>
    </aside>

    <!-- 右：图库网格 + 分页 -->
    <div class="flex min-w-0 flex-1 flex-col gap-3">
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
        <div class="flex items-center gap-2">
          <span class="text-[11px] text-ink-muted">上传至：{{ uploadTargetName }}</span>
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
      </div>

      <input ref="fileInput" type="file" accept="image/jpeg,image/png" multiple class="hidden" @change="onFilesPicked" />

      <p class="text-[11px] leading-relaxed text-ink-muted/80">
        上传自动压缩至 ≤180KB（B 平台提交口径）；轮回使用的图片消费后进入「已使用」保留不删；图库中「删除」会移入回收站，回收站内「删除」才永久移除（保留 7 天后也会自动清除）；点击图片打开灯箱预览，可缩放、左右切换。
      </p>

      <div class="xb-scroll min-h-[56vh] max-h-[72vh] overflow-y-auto overflow-x-hidden rounded-xl bg-cloud/40 px-1.5 py-1.5">
        <div v-if="pagedList.length === 0" class="flex min-h-[52vh] items-center justify-center text-sm text-ink-muted">
          {{ view === 'trash' ? '回收站为空' : view === 'used' ? '已使用列表为空' : '当前分组暂无图片' }}
        </div>
      <div v-else class="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-5">
        <div
          v-for="img in pagedList"
          :key="img.id"
          class="group overflow-hidden rounded-xl border border-ink/10 bg-white"
          :draggable="!img.inTrash"
          @dragstart="onDragStart(img, $event)"
          @dragend="onDragEnd"
        >
          <div class="relative aspect-[4/3] overflow-hidden bg-gradient-to-br from-cloud to-brand/10">
            <img
              v-if="urls[img.id]"
              :src="urls[img.id]"
              class="h-full w-full cursor-zoom-in object-contain transition duration-200 group-hover:scale-105"
              alt=""
              @click="openPreview(img)"
            />
            <Icon v-else name="image" :size="26" class="absolute inset-0 m-auto text-ink-muted" />
            <div
              v-if="urls[img.id]"
              class="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition group-hover:bg-black/30 group-hover:opacity-100"
            >
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-lg bg-white/90 px-2.5 py-1 text-xs text-ink shadow-sm hover:bg-white"
                @click.stop="openPreview(img)"
              >
                <Icon name="search" :size="13" />预览
              </button>
            </div>
            <span
              v-if="groupNameOf(img)"
              class="absolute left-1.5 top-1.5 rounded-md bg-black/45 px-1.5 py-0.5 text-[10px] text-white"
            >{{ groupNameOf(img) }}</span>
            <span v-if="!img.inTrash" class="absolute right-1.5 top-1.5 rounded-md bg-black/45 px-1.5 py-0.5 text-[10px] text-white opacity-0 transition group-hover:opacity-100">
              拖动到左侧分组可移动
            </span>
          </div>
          <div class="flex items-center justify-between gap-1 px-2 py-1.5">
            <p class="min-w-0 flex-1 truncate text-xs text-ink-soft" :title="img.name">{{ img.name }}</p>
            <span class="shrink-0 text-[11px] text-ink-muted">{{ img.sizeKb }}KB</span>
          </div>
          <div class="flex items-center justify-end gap-2 border-t border-ink/5 px-2 py-1.5">
            <template v-if="movingId === img.id">
              <BaseSelect v-model="moveTargetId" :options="moveOptions" :searchable="true" size="sm" class="min-w-0 flex-1" />
              <button class="shrink-0 text-[11px] text-brand hover:underline" @click="confirmMove">确定</button>
              <button class="shrink-0 text-[11px] text-ink-muted hover:underline" @click="movingId = null">取消</button>
            </template>
            <template v-else-if="view === 'used'">
              <button class="text-[11px] text-info hover:underline" @click="restore(img.id)">恢复至图库</button>
              <button class="text-[11px] text-ink-muted hover:text-brand" @click="startMove(img)">移动</button>
            </template>
            <template v-else-if="view === 'active'">
              <button class="text-[11px] text-ink-muted hover:text-brand" @click="startMove(img)">移动</button>
              <button class="text-[11px] text-ink-muted hover:text-brand" @click="markUsed(img.id)">标记已用</button>
              <button class="text-[11px] text-danger hover:underline" @click="toTrash(img.id)">删除</button>
            </template>
            <template v-else>
              <button class="text-[11px] text-info hover:underline" @click="restore(img.id)">恢复</button>
              <button class="text-[11px] text-danger hover:underline" @click="askDelete(img)">删除</button>
            </template>
          </div>
        </div>
      </div>
      </div>

      <div v-if="total > 0" class="mt-auto flex justify-center border-t border-ink/5 pt-3">
        <BasePagination :page="page" :page-size="pageSize" :total="total" :page-size-options="[12, 24, 48, 96]" @update:page="page = $event" @update:pageSize="onPageSizeChange" />
      </div>
    </div>

    <!-- 回收站删除二次确认 -->
    <ConfirmModal
      v-model="showDelConfirm"
      title="确认删除图片"
      :message="pendingDelete ? `「${pendingDelete.name}」删除后将从磁盘永久移除且不可恢复，确定要删除吗？` : ''"
      icon="trash"
      danger
      confirm-text="删除"
      :confirming="deleting"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch, onBeforeUnmount } from 'vue'
import PhotoSwipeLightbox from 'photoswipe/lightbox'
import PhotoSwipe from 'photoswipe'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import BasePagination from '@/components/BasePagination.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { fetchImageBlobUrl } from '@/api/signConfig'
import toast from '@/utils/toast'

const store = useSignConfigStore()
const view = ref('active')
const views = [
  { value: 'active', label: '图库' },
  { value: 'used', label: '已使用' },
  { value: 'trash', label: '回收站' }
]

// ── 分组（左栏）：groupFilter 为 'all' | 'ungrouped' | 分组 id（数字）；
// 分组名由用户自建（如寝室号"3栋507"），同寝室账号共用同一分组 ──
const groupFilter = ref('all')
const groupQuery = ref('')
const creating = ref(false)
const newName = ref('')
const editingGroupId = ref(null)
const editingName = ref('')

// 分组搜索：按名称包含匹配（大小写不敏感），命中行为空时视为全显
const groupQueryHit = (name) => {
  const q = groupQuery.value.trim().toLowerCase()
  return !q || String(name).toLowerCase().includes(q)
}
const matchesGroupQuery = groupQueryHit
const visibleGroups = computed(() => store.imageGroups.filter((g) => groupQueryHit(g.name)))
const groupsEmpty = computed(() => visibleGroups.value.length === 0)

// 当前视图下的图片池（视图感知：图库=active，已使用=used，回收站=trash）
const viewPool = computed(() => {
  const v = view.value
  return store.imageLibrary.filter((i) => {
    if (v === 'trash') return i.inTrash
    if (v === 'used') return i.used
    return !i.inTrash && !i.used
  })
})
const counts = computed(() => {
  const byGroup = { all: viewPool.value.length, ungrouped: 0 }
  for (const g of store.imageGroups) byGroup[g.id] = 0
  for (const i of viewPool.value) {
    if (i.groupId == null) byGroup.ungrouped += 1
    else if (byGroup[i.groupId] != null) byGroup[i.groupId] += 1
  }
  return byGroup
})
// 图片角标的所属分组名
const groupNameOf = (img) => {
  const g = store.imageGroups.find((x) => x.id === img.groupId)
  return g ? g.name : ''
}

const list = computed(() => {
  const pool = viewPool.value
  if (groupFilter.value === 'all') return pool
  if (groupFilter.value === 'ungrouped') return pool.filter((i) => i.groupId == null)
  return pool.filter((i) => i.groupId === groupFilter.value)
})

// 新建/重命名分组
async function confirmCreate() {
  const name = newName.value.trim()
  if (!name) {
    toast('请填写分组名称', 'error')
    return
  }
  const groups = await store.createImageGroup(name)
  const last = groups[groups.length - 1]
  if (last) groupFilter.value = last.id
  creating.value = false
  newName.value = ''
  toast('分组已创建', 'success')
}
function startRename(g) {
  editingGroupId.value = g.id
  editingName.value = g.name
}
async function confirmRename() {
  const name = editingName.value.trim()
  if (!name) {
    toast('请填写分组名称', 'error')
    return
  }
  await store.renameImageGroup(editingGroupId.value, name)
  editingGroupId.value = null
  toast('分组已重命名', 'success')
}
async function removeGroup(g) {
  // 图片回落未分组（不随组删除），无数据损失
  await store.deleteImageGroup(g.id)
  if (groupFilter.value === g.id) groupFilter.value = 'all'
  toast('分组已删除，组内图片移至未分组', 'success')
}

// ── 上传：目标为当前分组（全部/未分组视图下归未分组）──
const fileInput = ref(null)
const uploading = ref(false)
const uploadTargetName = computed(() => {
  if (typeof groupFilter.value === 'number') {
    const g = store.imageGroups.find((x) => x.id === groupFilter.value)
    return g ? g.name : '未分组'
  }
  return '未分组'
})
const uploadGroupId = computed(() => (typeof groupFilter.value === 'number' ? groupFilter.value : null))

async function onFilesPicked(e) {
  const files = Array.from(e.target.files || [])
  e.target.value = ''
  if (!files.length) return
  uploading.value = true
  let okCount = 0
  try {
    for (const f of files) {
      try {
        await store.uploadImage(f, uploadGroupId.value)
        okCount += 1
      } catch (err) {
        toast(`「${f.name}」上传失败：${err.message || '未知错误'}`, 'error')
      }
    }
    if (okCount) toast(`已上传 ${okCount} 张图片至「${uploadTargetName.value}」`, 'success')
  } finally {
    uploading.value = false
  }
}

// ── 拖拽移动（C1 原生 HTML5）：拖卡片 → 放到左栏分组行 ──
const draggingId = ref(null)
const dropKey = ref(null)
function onDragStart(img, e) {
  draggingId.value = img.id
  e.dataTransfer.setData('text/plain', String(img.id)) // Firefox 需要数据才允许拖放
  e.dataTransfer.effectAllowed = 'move'
}
function onDragEnd() {
  draggingId.value = null
  dropKey.value = null
}
async function onDropTo(key) {
  const img = store.imageLibrary.find((i) => i.id === draggingId.value)
  const target = key === 'ungrouped' ? null : key
  draggingId.value = null
  dropKey.value = null
  if (!img || img.groupId === target) return
  await store.moveImage(img.id, target)
  toast('已移动到目标分组', 'success')
}

// ── 移动（兜底）：可搜索下拉，BaseSelect 面板 Teleport 到 body 不会被卡片裁切 ──
const movingId = ref(null)
const moveTargetId = ref('')
const moveOptions = computed(() => [
  { label: '未分组', value: '' },
  ...store.imageGroups.map((g) => ({ label: g.name, value: String(g.id) }))
])
function startMove(img) {
  movingId.value = img.id
  moveTargetId.value = img.groupId == null ? '' : String(img.groupId)
}
async function confirmMove() {
  const target = moveTargetId.value === '' ? null : Number(moveTargetId.value)
  await store.moveImage(movingId.value, target)
  movingId.value = null
  toast('已移动到目标分组', 'success')
}

// ── 缩略图：blob objectURL 会话级缓存 ──
const urls = reactive({})

// ── 图片原始尺寸缓存 ──
// PhotoSwipe v5 必须显式给出 width/height：缺失时它无从判断原始比例，会退回按视口铺满，
// 图片因此被拉伸变形；缩放级别也由该尺寸推算，缺失会导致滚轮缩放失效。
// 尺寸取自 blob 自身的 naturalWidth/Height，与灯箱实际展示的图同源，不受缩略图缩放影响。
const sizeCache = reactive({})
function probeSize(src) {
  if (!sizeCache[src]) {
    sizeCache[src] = new Promise((resolve) => {
      const im = new Image()
      im.onload = () => resolve({ width: im.naturalWidth || 0, height: im.naturalHeight || 0 })
      im.onerror = () => resolve({ width: 0, height: 0 })
      im.src = src
    })
  }
  return sizeCache[src]
}

// ── 分页：前端分页（图库上限 50 张），翻页后预览范围与所见一致 ──
const page = ref(1)
const pageSize = ref(24)
const total = computed(() => list.value.length)
const pagedList = computed(() => list.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
watch([groupFilter, view, () => store.imageLibrary.length], () => { page.value = 1 })
// 当前页图片被移走/删除导致页码越界时回退到第一页
watch(total, (t) => {
  if (page.value > Math.max(1, Math.ceil(t / pageSize.value))) page.value = 1
})
function onPageSizeChange(size) {
  pageSize.value = size
  page.value = 1
}

// 缩略图预取：只拉当前页，翻页时增量加载
watch(pagedList, async (rows) => {
  for (const r of rows) {
    if (!urls[r.id]) {
      try { urls[r.id] = await fetchImageBlobUrl(r.id) } catch { /* 文件丢失时留图标占位 */ }
    }
    // 预热尺寸，打开灯箱时命中缓存无需等待
    if (urls[r.id]) probeSize(urls[r.id])
  }
}, { immediate: true })

// ── 全屏灯箱（PhotoSwipeLightbox）：带默认 UI（关闭/缩放按钮、左右箭头、计数器）；
// 灯箱范围 = 当前页全部图片，打开前确保缩略图 url 已就绪 ──
let lightbox = null
async function openPreview(img) {
  await Promise.all(pagedList.value.map(async (r) => {
    if (!urls[r.id]) {
      try { urls[r.id] = await fetchImageBlobUrl(r.id) } catch { /* 占位图标 */ }
    }
  }))
  const rows = pagedList.value.filter((r) => urls[r.id])
  const sizes = await Promise.all(rows.map((r) => probeSize(urls[r.id])))
  // 带 width/height 后 PhotoSwipe 按原始宽高比居中适配，不再铺满拉伸；缩放级别亦由此推算
  const dataSource = rows.map((r, i) => {
    const { width, height } = sizes[i]
    return width && height ? { src: urls[r.id], width, height } : { src: urls[r.id] }
  })
  const index = dataSource.findIndex((d) => d.src === urls[img.id])
  if (!dataSource.length || index === -1) return
  // 每次打开都新建实例，先销毁旧的，避免残留 DOM 与事件监听
  lightbox?.destroy()
  lightbox = new PhotoSwipeLightbox({
    dataSource,
    index,
    showHideAnimationType: 'fade',
    wheelToZoom: true,
    pswpModule: PhotoSwipe
  })
  lightbox.init()
  lightbox.loadAndOpen(index)
}
onBeforeUnmount(() => { lightbox?.destroy() })

function toTrash(id) { store.trashImage(id) }
function restore(id) { store.restoreImage(id) }
function remove(id) { store.deleteImage(id) }
function markUsed(id) { store.markUsed(id) }

// 回收站删除二次确认：确认后物理删除（不可恢复）
const pendingDelete = ref(null)
const showDelConfirm = ref(false)
const deleting = ref(false)
function askDelete(img) {
  pendingDelete.value = img
  showDelConfirm.value = true
}
async function confirmDelete() {
  if (!pendingDelete.value) return
  deleting.value = true
  try {
    await remove(pendingDelete.value.id)
    showDelConfirm.value = false
    pendingDelete.value = null
  } finally {
    deleting.value = false
  }
}
</script>
