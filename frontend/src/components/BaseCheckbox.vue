<template>
  <label
    class="group inline-flex cursor-pointer select-none items-center gap-2.5"
    :class="{ 'cursor-not-allowed opacity-60': disabled }"
  >
    <span class="relative inline-flex h-5 w-5 shrink-0 items-center justify-center">
      <input
        type="checkbox"
        class="peer absolute inset-0 z-10 h-full w-full cursor-pointer rounded-[5px] opacity-0"
        :checked="modelValue"
        :disabled="disabled"
        @change="$emit('update:modelValue', $event.target.checked)"
      />
      <span
        class="pointer-events-none absolute inset-0 rounded-[5px] border-2 border-ink/25 bg-white transition-[background-color,border-color] duration-200 ease-out peer-checked:border-brand peer-checked:bg-brand peer-focus-visible:ring-[3px] peer-focus-visible:ring-brand/40"
      ></span>
      <svg
        class="check-mark pointer-events-none relative h-3 w-3 text-white"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="3.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M5 12.5 L10 17.5 L19 7" />
      </svg>
    </span>
    <span v-if="label" class="text-sm text-ink-muted">{{ label }}</span>
  </label>
</template>

<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  label: { type: String, default: '' },
  disabled: { type: Boolean, default: false }
})
defineEmits(['update:modelValue'])
</script>

<style scoped>
/* 对勾描边绘制：未勾选时收起，勾选时画出，呼应品牌区的打卡对勾母题 */
.check-mark path {
  stroke-dasharray: 26;
  stroke-dashoffset: 26;
  transition: stroke-dashoffset 0.28s ease-out;
}
.peer:checked ~ .check-mark path {
  stroke-dashoffset: 0;
}
</style>
