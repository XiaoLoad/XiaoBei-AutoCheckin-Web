<template>
  <BaseModal v-model="open" :title="title" size="sm">
    <div class="flex items-start gap-3">
      <span
        class="grid h-10 w-10 shrink-0 place-items-center rounded-full"
        :class="theme.wrap"
      >
        <Icon :name="theme.icon" :size="20" :class="theme.iconCls" />
      </span>
      <p class="min-w-0 pt-1 text-sm leading-relaxed text-ink-soft">{{ message }}</p>
    </div>

    <template #footer>
      <button
        type="button"
        class="w-full rounded-xl px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/20 transition hover:opacity-90"
        :class="theme.btn"
        @click="close"
      >
        {{ confirmText }}
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed } from 'vue'
import BaseModal from '@/components/BaseModal.vue'
import Icon from '@/components/Icon.vue'

// 通用消息模态框：统一替代散落各处的原生 alert / 浏览器默认弹窗。
// 用法：<MessageModal v-model="show" type="error" title="登录失败" message="密码错误" />
// type 决定图标与配色：success / warning / error / info
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  type: { type: String, default: 'info' },
  title: { type: String, default: '' },
  message: { type: String, default: '' },
  confirmText: { type: String, default: '我知道了' }
})
const emit = defineEmits(['update:modelValue', 'close'])

const open = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const theme = computed(
  () =>
    ({
      success: { icon: 'check-circle', wrap: 'bg-success/10', iconCls: 'text-success', btn: 'bg-success' },
      warning: { icon: 'alert', wrap: 'bg-amber/15', iconCls: 'text-amber', btn: 'bg-amber' },
      error: { icon: 'x-circle', wrap: 'bg-danger/10', iconCls: 'text-danger', btn: 'bg-danger' },
      info: { icon: 'info', wrap: 'bg-brand/10', iconCls: 'text-brand', btn: 'bg-brand' }
    }[props.type] || {
      icon: 'info',
      wrap: 'bg-brand/10',
      iconCls: 'text-brand',
      btn: 'bg-brand'
    })
)

function close() {
  emit('update:modelValue', false)
  emit('close')
}
</script>
