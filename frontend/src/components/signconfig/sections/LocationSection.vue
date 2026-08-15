<template>
  <ConfigSection title="位置配置" icon="map-pin" :source="source">
    <div class="space-y-3">
      <div class="flex items-end gap-2">
        <div class="flex-1">
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
          class="inline-flex h-[38px] items-center gap-1.5 rounded-lg border border-ink/10 px-3 text-sm text-ink-soft transition hover:bg-cloud"
          @click="store.gotoResource('locations')"
        >
          <Icon name="layers" :size="14" />管理
        </button>
      </div>

      <div v-if="selected" class="space-y-0.5 rounded-lg bg-cloud/60 px-3 py-2 text-xs text-ink-soft">
        <p>名称：<span class="font-medium text-ink">{{ selected.name }}</span>（须与地址对应）</p>
        <p class="truncate">地址：{{ selected.address }}</p>
        <p>经纬度：{{ selected.lat }}, {{ selected.lng }} · 坐标偏移 {{ selected.offset }} 米</p>
      </div>
      <p v-else class="text-xs text-ink-muted">未指定位置；可在「位置池」中添加平台预设位置或我的位置。</p>
    </div>
  </ConfigSection>
</template>

<script setup>
import { computed } from 'vue'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import Icon from '@/components/Icon.vue'
import { useSignConfigStore } from '@/stores/signConfig'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' }
})

const store = useSignConfigStore()
const selected = computed(() => {
  const id = props.config.locationId
  if (!id) return null
  return store.systemLocations.find((l) => l.id === id) || store.userLocations.find((l) => l.id === id) || null
})
</script>
