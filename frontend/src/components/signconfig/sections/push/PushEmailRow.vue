<template>
  <!-- 邮件通道的落位体：邮件通道的差异只在收件邮箱（账号自填 > 所用凭证的默认收件邮箱），
       所以这里问的是「发给谁」，而不是像 token 型通道那样问「绑没绑」。 -->
  <div class="space-y-1.5">
    <div v-if="audit.needsSender" class="flex items-center gap-2">
      <span class="shrink-0 text-[11px] text-ink-muted">发件凭证</span>
      <PushCredPick
        :model-value="pickerValue"
        :options="options"
        placeholder="选择邮件凭证"
        empty-text="暂无邮件凭证，去新建"
        @update:model-value="(v) => emit('update:modelValue', v)"
        @create="emit('create')"
      />
    </div>

    <div v-if="scope === 'account'" class="flex items-baseline gap-2">
      <span class="shrink-0 text-[11px] text-ink-muted">收件邮箱</span>
      <span class="min-w-0 break-all text-[11px]" :class="audit.to ? 'text-ink-soft' : 'text-danger-ink'">
        {{ audit.to || '没有收件邮箱' }}
      </span>
      <span v-if="audit.to" class="ml-auto shrink-0 text-[10px] text-ink-muted">{{ srcLabel(audit.src) }}</span>
    </div>

    <template v-else>
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="inline-flex items-center gap-1 text-[11px] font-medium text-brand transition hover:text-brand-dark"
          :aria-expanded="open"
          @click="open = !open"
        >
          各账号收件邮箱
          <Icon name="chevron-down" :size="11" :class="open && 'rotate-180'" />
        </button>
        <span class="text-[10px] text-ink-muted">{{ audit.rows.length }} 个账号</span>
      </div>
      <GCollapse :show="open">
        <ul class="max-h-44 space-y-0.5 overflow-auto pt-1">
          <li v-for="r in audit.rows" :key="r.id" class="flex items-baseline gap-2 text-[11px]">
            <span class="w-20 shrink-0 truncate text-ink-soft" :title="r.name">{{ r.name }}</span>
            <span class="min-w-0 flex-1 truncate" :class="r.to ? 'text-ink-muted' : 'text-danger-ink'">{{ r.to || '跳过' }}</span>
            <span class="shrink-0 text-[10px] text-ink-muted">{{ srcLabel(r.src) }}</span>
          </li>
        </ul>
      </GCollapse>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import GCollapse from '@/components/signconfig/GCollapse.vue'
import Icon from '@/components/Icon.vue'
import PushCredPick from '@/components/signconfig/sections/push/PushCredPick.vue'

defineProps({
  // 核对结论：auditEmailChannel（配置套）或 auditAccountEmail（账号）的返回值
  audit: { type: Object, required: true },
  options: { type: Array, default: () => [] },
  pickerValue: { type: [String, Number, null], default: '' },
  // set 配置套视角（逐账号落点明细）/ account 单账号视角（只给一条实际结论）
  scope: { type: String, default: 'set' }
})
const emit = defineEmits(['update:modelValue', 'create'])

const open = ref(false)

const SRC_LABELS = {
  account: '账号自填',
  'own-cred': '自带凭证的默认收件邮箱',
  'shared-cred': '共用凭证的默认收件邮箱',
  none: '发不出去'
}
function srcLabel(src) {
  return SRC_LABELS[src] || ''
}
</script>
