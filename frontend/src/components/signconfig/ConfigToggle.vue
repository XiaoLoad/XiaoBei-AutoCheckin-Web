<template>
  <button
    type="button"
    role="switch"
    :aria-checked="modelValue"
    class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors"
    :class="modelValue ? 'bg-brand' : 'bg-ink/15'"
    @click="toggle"
  >
    <span
      class="inline-block h-5 w-5 transform rounded-full bg-elevated shadow transition-transform"
      :class="modelValue ? 'translate-x-[22px]' : 'translate-x-0.5'"
    />
  </button>
</template>

<script setup>
const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue'])
function toggle() {
  emit('update:modelValue', !props.modelValue)
}
</script>
