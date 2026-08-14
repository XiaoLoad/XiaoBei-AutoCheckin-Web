<template>
  <div class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
    <h3 class="font-semibold text-gray-800">{{ title }}</h3>
    <p class="mt-1 text-sm text-gray-500"><slot>示例卡片内容</slot></p>
  </div>
</template>

<script setup>
// 通用展示卡片组件（示例）
defineProps({
  title: {
    type: String,
    default: '标题'
  }
})
</script>
