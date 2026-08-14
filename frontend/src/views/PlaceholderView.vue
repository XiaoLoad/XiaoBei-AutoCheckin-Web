<template>
  <div class="dash-card flex flex-col items-center justify-center text-center py-20 px-6 fade-up">
    <div class="w-14 h-14 rounded-2xl bg-brand/10 text-brand grid place-items-center mb-4">
      <Icon name="settings" :size="28" />
    </div>
    <h2 class="text-lg font-semibold text-ink">{{ title }} · 建设中</h2>
    <p class="mt-2 text-sm text-ink-muted max-w-sm leading-relaxed">
      该模块尚未实现，当前为后台管理框架的占位页。后续将在此接入对应的业务功能。
    </p>
    <RouterLink to="/" class="mt-6 text-sm font-medium text-brand hover:underline">
      返回概览
    </RouterLink>
  </div>
</template>

<script setup>
import { useRoute, RouterLink } from 'vue-router'
import Icon from '@/components/Icon.vue'

const route = useRoute()
const title = route.meta?.title || '页面'
</script>
