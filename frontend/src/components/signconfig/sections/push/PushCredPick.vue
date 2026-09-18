<template>
  <!-- 单通道凭证选择器：池里没有该类型凭证时不给空下拉，直接把「去新建」摆在这里，
       免得勾了通道却卡在一个选不出东西的控件上 -->
  <BaseSelect
    v-if="options.length"
    :model-value="modelValue"
    :options="options"
    :searchable="options.length > 6"
    placement="auto"
    size="sm"
    :placeholder="placeholder"
    class="min-w-0 flex-1"
    @update:model-value="(v) => emit('update:modelValue', v)"
  />
  <button
    v-else
    type="button"
    class="flex min-w-0 flex-1 items-center justify-center gap-1 rounded-xl border border-dashed border-amber/40 bg-amber/10 px-3 py-1.5 text-xs text-amber-ink transition hover:bg-amber/15"
    @click="emit('create')"
  >
    <Icon name="plus" :size="13" />{{ emptyText }}
  </button>
</template>

<script setup>
import BaseSelect from '@/components/BaseSelect.vue'
import Icon from '@/components/Icon.vue'

defineProps({
  modelValue: { type: [String, Number, null], default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '选择凭证' },
  emptyText: { type: String, default: '暂无凭证，去新建' }
})
const emit = defineEmits(['update:modelValue', 'create'])
</script>
