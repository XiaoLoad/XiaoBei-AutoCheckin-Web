<template>
  <ConfigSection title="位置配置" icon="map-pin" :source="source" :error="error" :required="required">
    <div class="space-y-3">
      <div class="flex items-end gap-2">
        <div class="min-w-0 flex-1">
          <label class="mb-1 block text-xs font-medium text-ink-muted">签到位置（从位置池选择其一）</label>
          <BaseSelect
            v-model="config.locationId"
            :options="store.locationOptions"
            :searchable="true"
            placeholder="选择位置"
            size="sm"
          />
        </div>
        <button
          type="button"
          class="inline-flex h-[38px] shrink-0 items-center gap-1.5 rounded-lg border border-ink/10 px-3 text-sm text-ink-soft transition hover:bg-cloud"
          @click="store.gotoResource('locations')"
        >
          <Icon name="layers" :size="14" />管理
        </button>
      </div>

      <div v-if="selected" class="space-y-0.5 rounded-lg bg-cloud/60 px-3 py-2 text-xs text-ink-soft">
        <p>名称：<span class="font-medium text-ink">{{ selected.name }}</span></p>
        <p class="truncate">地址：{{ selected.address }}</p>
        <p>经纬度：{{ selected.lat }}, {{ selected.lng }} · 坐标偏移 {{ selected.offset }} 米</p>
      </div>
      <p v-else class="text-xs text-ink-muted">尚未选择位置（必填项）。可在「位置池」中添加平台预设位置或我的位置后从上方下拉选择。</p>

      <!-- 围栏拦截开关（fence.intercept）：提交前校验配置位置是否落在任务围栏内，防异常位置暴露 -->
      <div class="flex items-center justify-between gap-3 rounded-lg bg-cloud/60 px-3 py-2.5">
        <div class="min-w-0">
          <p class="text-xs font-medium text-ink-soft">围栏拦截</p>
          <p class="mt-0.5 text-[11px] leading-relaxed text-ink-muted">
            提交前校验所选位置是否在任务围栏半径内，超出则不提交并给出提示，防止异常位置暴露风险。关闭后不校验、照常提交。
          </p>
        </div>
        <ConfigToggle v-model="config.fence.intercept" class="shrink-0" />
      </div>
    </div>
  </ConfigSection>
</template>

<script setup>
import { computed } from 'vue'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import ConfigToggle from '@/components/signconfig/ConfigToggle.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import Icon from '@/components/Icon.vue'
import { useSignConfigStore } from '@/stores/signConfig'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' },
  error: { type: String, default: '' },
  required: { type: Boolean, default: false }
})

const store = useSignConfigStore()

// 旧配置（无 fence 块）兜底：本段直接改写 config（既定草稿编辑模式），补默认开启
if (!props.config.fence) props.config.fence = { intercept: true }

const selected = computed(() => {
  const id = props.config.locationId
  if (!id) return null
  return store.systemLocations.find((l) => l.id === id) || store.userLocations.find((l) => l.id === id) || null
})
</script>
