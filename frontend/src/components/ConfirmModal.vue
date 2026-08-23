<template>
  <!-- 通用确认弹窗：Teleport 到 body，避免被父级 overflow/transform 裁剪 -->
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-[1000] flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
      >
        <!-- 遮罩层：点击关闭（受 closeOnOverlay 控制） -->
        <div class="absolute inset-0 bg-ink/50 backdrop-blur-[2px]" @click="onOverlayClick" />

        <!-- 弹窗主体 -->
        <div
          class="modal-panel relative flex max-h-[90vh] w-full max-w-sm flex-col overflow-hidden rounded-2xl bg-white shadow-2xl shadow-ink/20"
          @click.stop
        >
          <!-- 标题区 -->
          <div class="flex shrink-0 items-start gap-3 px-5 pt-5">
            <span
              v-if="icon"
              class="grid h-10 w-10 shrink-0 place-items-center rounded-full"
              :class="danger ? 'bg-danger/10 text-danger' : 'bg-brand/10 text-brand'"
            >
              <Icon :name="icon" :size="20" />
            </span>
            <h3 class="flex-1 pt-1.5 text-base font-semibold text-ink">
              {{ title }}
            </h3>
            <button
              v-if="showClose"
              type="button"
              class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud hover:text-ink"
              aria-label="关闭"
              @click="onCancel"
            >
              <Icon name="close" :size="18" />
            </button>
          </div>

          <!-- 内容区：默认展示 message，也支持具名插槽自定义 -->
          <div class="flex-1 min-h-0 overflow-y-auto px-5 pb-5 pt-2 text-sm leading-relaxed text-ink-muted">
            <slot>{{ message }}</slot>
          </div>

          <!-- 操作区 -->
          <div class="flex shrink-0 gap-3 px-5 pb-5">
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
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { watch, onBeforeUnmount } from 'vue'
import Icon from '@/components/Icon.vue'

// 通用确认弹窗：通过 v-model 控制显隐，confirm/cancel 事件由调用方处理业务逻辑。
// 设计目标：可抽离为独立复用组件，任何需要「二次确认」的场景（删除、退出、授权等）均可调用。
const props = defineProps({
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

function close() {
  emit('update:modelValue', false)
}

function onOverlayClick() {
  if (props.closeOnOverlay) onCancel()
}

function onCancel() {
  emit('cancel')
  close()
}

// 确认：仅抛出事件，由调用方决定何时关闭（如异步完成后）
function onConfirm() {
  emit('confirm')
}

function onKeydown(e) {
  if (e.key === 'Escape' && props.modelValue && props.closeOnEsc) onCancel()
}

// 打开时锁定页面滚动并监听 ESC；关闭时恢复
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

<style scoped>
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
