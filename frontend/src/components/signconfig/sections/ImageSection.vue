<template>
  <ConfigSection title="图片策略" icon="image" :source="source">
    <div class="space-y-3">
      <div class="flex items-center justify-between gap-3">
        <div>
          <p class="text-sm font-medium text-ink">上传图片</p>
          <p class="text-xs text-ink-muted">开启后签到时按策略消费图库图片</p>
        </div>
        <ConfigToggle v-model="config.image.enabled" />
      </div>

      <GCollapse :show="config.image.enabled">
        <div class="space-y-2 pt-1">
          <div>
            <label class="mb-1 block text-xs font-medium text-ink-muted">图片来源分组</label>
            <BaseSelect v-model="config.image.groupId" :options="groupOptions" :searchable="true" size="sm" class="w-72" />
            <p class="mt-1 text-xs text-ink-muted">只使用所选分组内的照片；同寝室账号选同一分组即共用。分组在「我的资源 → 图库」中管理。</p>
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-ink-muted">图片策略</label>
            <BaseSelect v-model="config.image.strategy" :options="strategyOptions" size="sm" class="w-72" />
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-ink-muted">图库 {{ activeCount }} 张（回收站 {{ trashCount }} 张）</span>
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-lg border border-ink/10 px-3 py-1.5 text-sm text-ink-soft transition hover:bg-cloud"
              @click="store.gotoResource('images')"
            >
              <Icon name="image" :size="14" />管理图库
            </button>
          </div>
        </div>
      </GCollapse>
    </div>
  </ConfigSection>
</template>

<script setup>
import { computed } from 'vue'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import ConfigToggle from '@/components/signconfig/ConfigToggle.vue'
import GCollapse from '@/components/signconfig/GCollapse.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import Icon from '@/components/Icon.vue'
import { useSignConfigStore } from '@/stores/signConfig'

defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' }
})

const store = useSignConfigStore()
const strategyOptions = [
  { label: '循环复用（用毕入回收站续用）', value: 'recycle' },
  { label: '用后删除', value: 'delete' },
  { label: '用后入回收站可恢复', value: 'trash' }
]
const activeCount = computed(() => store.imageLibrary.filter((i) => !i.inTrash).length)
const trashCount = computed(() => store.imageLibrary.filter((i) => i.inTrash).length)
// 图片来源分组选项：'' = 全部图库（兼容未分组的历史配置），其余为用户自建分组（如寝室号）
const groupOptions = computed(() => [
  { label: '全部图库', value: '' },
  ...store.imageGroups.map((g) => ({ label: g.name, value: g.id }))
])
</script>
