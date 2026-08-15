<template>
  <ConfigSection title="高级设置" icon="settings" :source="source">
    <div class="space-y-3">
      <div>
        <label class="mb-1 block text-xs font-medium text-ink-muted">User-Agent（机型模板）</label>
        <BaseSelect
          v-model="config.advanced.uaTemplateId"
          :options="store.uaOptions"
          :searchable="true"
          placeholder="选择 UA 模板或自定义"
          size="sm"
          class="w-72"
        />
      </div>
      <div v-if="!config.advanced.uaTemplateId">
        <label class="mb-1 block text-xs font-medium text-ink-muted">自定义 UA</label>
        <textarea
          v-model="config.advanced.customUa"
          rows="2"
          class="w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
          placeholder="粘贴自定义 User-Agent 字符串"
        />
      </div>
      <div v-else class="break-all rounded-lg bg-cloud/60 px-3 py-2 text-xs text-ink-soft">
        {{ uaPreview }}
      </div>
    </div>
  </ConfigSection>
</template>

<script setup>
import { computed } from 'vue'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import { useSignConfigStore } from '@/stores/signConfig'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' }
})

const store = useSignConfigStore()
const uaPreview = computed(() => {
  const t = store.uaTemplates.find((u) => u.id === props.config.advanced.uaTemplateId)
  return t ? t.ua : '未找到对应模板'
})
</script>
