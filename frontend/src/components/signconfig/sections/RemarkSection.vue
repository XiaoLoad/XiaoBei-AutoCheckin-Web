<template>
  <ConfigSection title="备注列表" icon="file" :source="source">
    <p class="mb-2 text-xs text-ink-muted">签到时后台随机选取一条提交；可按 B 平台账号设置带名备注（如"xxx签到"）。</p>
    <div class="space-y-2">
      <div v-for="(r, i) in config.remarks" :key="i" class="flex items-center gap-2">
        <input
          v-model="config.remarks[i]"
          class="flex-1 rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
          placeholder="输入备注内容"
        />
        <button
          type="button"
          class="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-ink/10 text-ink-muted transition hover:bg-danger/10 hover:text-danger"
          aria-label="删除备注"
          @click="config.remarks.splice(i, 1)"
        >
          <Icon name="trash" :size="15" />
        </button>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-ink/20 px-3 py-2 text-sm text-ink-soft transition hover:bg-cloud"
        @click="config.remarks.push('')"
      >
        <Icon name="plus" :size="15" />添加备注
      </button>
    </div>
  </ConfigSection>
</template>

<script setup>
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import Icon from '@/components/Icon.vue'

defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' }
})
</script>
