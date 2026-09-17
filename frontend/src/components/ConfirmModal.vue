<template>
  <!-- 通用确认弹窗：基于 BaseModal 组装（遮罩/ESC/滚动锁定/过渡均由骨架提供）。
       任何需要「二次确认」的场景（删除、退出、授权等）均可调用。 -->
  <BaseModal
    :model-value="modelValue"
    size="sm"
    :hide-close="!showClose"
    :close-on-overlay="closeOnOverlay"
    :close-on-esc="closeOnEsc"
    @update:model-value="(v) => emit('update:modelValue', v)"
    @cancel="onCancel"
  >
    <template #title>
      <span
        v-if="icon"
        class="grid h-10 w-10 shrink-0 place-items-center rounded-full"
        :class="danger ? 'bg-danger/10 text-danger' : 'bg-brand/10 text-brand'"
      >
        <Icon :name="icon" :size="20" />
      </span>
      <h3 class="flex-1 self-center pt-0.5 text-base font-semibold text-ink">
        {{ title }}
      </h3>
    </template>

    <!-- 内容区：默认展示 message，也支持插槽自定义 -->
    <div class="pt-1 text-sm leading-relaxed text-ink-muted">
      <slot>{{ message }}</slot>
    </div>

    <template #footer>
      <button
        type="button"
        class="flex-1 rounded-xl border border-ink/10 px-4 py-2.5 text-sm font-medium text-ink-soft transition hover:bg-cloud disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="confirming"
        @click="onCancel"
      >
        {{ cancelText }}
      </button>
      <button
        type="button"
        class="flex-1 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-70"
        :class="danger ? 'bg-danger hover:opacity-90' : 'bg-brand hover:bg-brand-dark'"
        :disabled="confirming"
        @click="onConfirm"
      >
        {{ confirming ? confirmingText : confirmText }}
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import BaseModal from '@/components/BaseModal.vue'
import Icon from '@/components/Icon.vue'

// 确认/取消事件由调用方处理业务逻辑；确认仅抛出事件，由调用方决定何时关闭（如异步完成后）。
defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '提示' },
  message: { type: String, default: '' },
  icon: { type: String, default: '' }, // 传空字符串可隐藏图标
  confirmText: { type: String, default: '确认' },
  cancelText: { type: String, default: '取消' },
  confirmingText: { type: String, default: '处理中…' },
  confirming: { type: Boolean, default: false }, // 异步处理中：禁用按钮并显示处理文案
  danger: { type: Boolean, default: false }, // 危险操作样式（红色）
  showClose: { type: Boolean, default: true }, // 是否显示右上角关闭按钮
  closeOnOverlay: { type: Boolean, default: true }, // 点击遮罩是否关闭
  closeOnEsc: { type: Boolean, default: true } // 按 ESC 是否关闭
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

function onConfirm() {
  emit('confirm')
}

function onCancel() {
  // 关闭弹窗（与遮罩 / ESC / 右上角 ✕ 同一条链路），并抛出 cancel 供调用方做清理
  emit('update:modelValue', false)
  emit('cancel')
}
</script>
