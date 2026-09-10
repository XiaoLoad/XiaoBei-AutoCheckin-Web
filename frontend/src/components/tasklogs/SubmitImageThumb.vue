<template>
  <div class="flex items-center gap-2.5">
    <!-- delete 策略：图片已被物理删除，无法回看 -->
    <template v-if="strategy === 'delete'">
      <span
        class="grid h-12 w-12 shrink-0 place-items-center rounded-lg border border-dashed border-ink/10 bg-cloud text-[11px] text-ink-muted"
        >已删除</span
      >
      <span class="text-xs text-ink-muted">图片已删除（用后删除策略）</span>
    </template>

    <!-- 有 image_id 且非 delete：经鉴权接口拉取 blob 后渲染缩略图 -->
    <template v-else-if="imageId">
      <button
        v-if="thumbUrl"
        type="button"
        class="relative h-12 w-12 shrink-0 overflow-hidden rounded-lg border border-ink/5 bg-cloud"
        title="点击查看大图"
        @click="open = true"
      >
        <img :src="thumbUrl" class="h-full w-full object-cover" alt="签到图片" />
      </button>
      <span
        v-else
        class="grid h-12 w-12 shrink-0 place-items-center rounded-lg border border-dashed border-ink/10 bg-cloud text-[11px] text-ink-muted"
        >{{ loading ? '加载中…' : '失效' }}</span
      >
      <span class="text-xs text-ink-muted">图片 ID {{ imageId }} · 策略 {{ strategyLabel }}</span>
    </template>

    <span v-else class="text-xs text-ink-muted">无图（未启用图库或任务无需图）</span>

    <!-- 大图预览：自包含遮罩，点击空白处关闭 -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="open && thumbUrl"
          class="fixed inset-0 z-50 flex items-center justify-center bg-ink/60 p-4"
          @click.self="open = false"
        >
          <img
            :src="thumbUrl"
            class="max-h-[85vh] max-w-[90vw] rounded-2xl bg-white shadow-2xl"
            alt="签到图片大图"
          />
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchImageBlobUrl } from '@/api/signConfig'

const props = defineProps({
  // 提交参数快照里的图库图片 id（recycle/trash 策略仍可看，delete 已物理删除）
  imageId: { type: [Number, String], default: null },
  // 用后策略：recycle / trash / delete
  strategy: { type: String, default: '' },
})

const STRATEGY_LABELS = { recycle: '循环复用', trash: '用后入回收站', delete: '用后删除' }
const strategyLabel = STRATEGY_LABELS[props.strategy] || props.strategy || '—'

const thumbUrl = ref('')
const loading = ref(false)
const open = ref(false)

// fetchImageBlobUrl 内部带 token 走 axios、用 responseType:'blob' 生成 objectURL，
// 并缓存于模块级 blobCache（与图库共用，不在此 revoke，避免误伤其它 <img>）。
onMounted(async () => {
  if (!props.imageId || props.strategy === 'delete') return
  loading.value = true
  try {
    thumbUrl.value = await fetchImageBlobUrl(props.imageId)
  } catch {
    // 文件丢失/无权限：留「失效」占位，不弹全局错误
    thumbUrl.value = ''
  } finally {
    loading.value = false
  }
})
</script>
