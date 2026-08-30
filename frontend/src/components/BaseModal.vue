<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-[1000] flex items-center justify-center p-4 max-sm:items-end max-sm:p-0"
        role="dialog"
        aria-modal="true"
      >
        <div class="absolute inset-0 bg-ink/50 backdrop-blur-[2px]" @click="onOverlayClick" />

        <div
          class="modal-panel relative flex w-full flex-col overflow-hidden rounded-2xl bg-white shadow-2xl shadow-ink/20 max-sm:rounded-b-none max-sm:rounded-t-2xl max-sm:max-h-[90dvh]"
          :class="[sizeClass, size === 'sm' ? 'max-h-[90vh]' : 'max-h-[92vh]']"
          @click.stop
        >
          <div class="flex shrink-0 items-center justify-between gap-3 px-5 pt-5">
            <slot name="title">
              <h3 class="text-base font-semibold text-ink">{{ title }}</h3>
            </slot>
            <button
              v-if="!hideClose"
              type="button"
              class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud hover:text-ink"
              aria-label="关闭"
              @click="onCancel"
            >
              <Icon name="close" :size="18" />
            </button>
          </div>

          <div class="flex-1 min-h-0 overflow-y-auto px-5 py-4">
            <slot />
          </div>

          <div v-if="$slots.footer" class="flex shrink-0 gap-3 border-t border-ink/5 px-5 py-4">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { watch, onBeforeUnmount, computed } from 'vue'
import Icon from '@/components/Icon.vue'

// 全站唯一弹窗骨架（ConfirmModal / UserFormModal / AccountFormModal 均基于本组件组装）。
// 显隐由 v-model 控制；关闭路径：遮罩点击（closeOnOverlay）、ESC（closeOnEsc）、右上角按钮
// （hideClose 隐藏）——三者统一走 cancel 语义，由调用方决定业务动作。
// 打开期间锁定页面滚动，关闭/卸载时恢复。
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  // sm=确认框(max-w-sm) / md=表单弹窗(max-w-md) / xl=宽表单(max-w-xl)
  size: { type: String, default: 'xl' },
  hideClose: { type: Boolean, default: false },
  closeOnOverlay: { type: Boolean, default: true },
  closeOnEsc: { type: Boolean, default: true }
})

const emit = defineEmits(['update:modelValue', 'close', 'cancel'])

const sizeClass = computed(
  () => ({ sm: 'max-w-sm', md: 'max-w-md', xl: 'max-w-xl' }[props.size] || 'max-w-xl')
)

function close() {
  emit('update:modelValue', false)
  emit('close')
}

function onCancel() {
  emit('cancel')
  close()
}

function onOverlayClick() {
  if (props.closeOnOverlay) onCancel()
}

function onKeydown(e) {
  if (e.key === 'Escape' && props.modelValue && props.closeOnEsc) onCancel()
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      document.body.style.overflow = 'hidden'
      window.addEventListener('keydown', onKeydown)
    } else {
      document.body.style.overflow = ''
      window.removeEventListener('keydown', onKeydown)
    }
  }
)

onBeforeUnmount(() => {
  document.body.style.overflow = ''
  window.removeEventListener('keydown', onKeydown)
})

// 暴露 close 以便调用方在异步完成后主动关闭
defineExpose({ close })
</script>

<style>
/*
 * 弹窗过渡样式为全站共享（Teleport 到 body 后scoped 属性不可靠），故放全局：
 * ConfirmModal / UserFormModal / AccountFormModal / AccountTaskConfigTab 内联弹窗
 * 均使用同一套 .modal-* Transition 名，禁止在各组件内重复定义。
 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active .modal-panel,
.modal-leave-active .modal-panel {
  transition: transform 0.22s ease, opacity 0.22s ease;
}
.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  transform: translateY(8px) scale(0.98);
  opacity: 0;
}
</style>
