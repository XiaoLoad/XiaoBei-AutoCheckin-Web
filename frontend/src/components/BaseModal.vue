<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-[1000] flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
      >
        <div class="absolute inset-0 bg-ink/50 backdrop-blur-[2px]" @click="close" />

        <div
          class="modal-panel relative flex max-h-[92vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl shadow-ink/20"
          @click.stop
        >
          <div class="flex items-center justify-between px-5 pt-5">
            <h3 class="text-base font-semibold text-ink">{{ title }}</h3>
            <button
              type="button"
              class="grid h-8 w-8 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud hover:text-ink"
              aria-label="关闭"
              @click="close"
            >
              <Icon name="close" :size="18" />
            </button>
          </div>

          <div class="overflow-y-auto px-5 py-4">
            <slot />
          </div>

          <div v-if="$slots.footer" class="flex gap-3 border-t border-ink/5 px-5 py-4">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import Icon from '@/components/Icon.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue', 'close'])

function close() {
  emit('update:modelValue', false)
  emit('close')
}
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
