<template>
  <!--
    布局分发：根据路由 meta.layout 选择布局组件。给布局加 :key="$route.path"，
    同布局内切换路由（如 / → /tasks）时路径变化会强制重建布局实例，
    其内部唯一的 <RouterView/> 随之重新渲染正确的路由组件，避免「地址变了但页面不切换」。
    各布局（DashboardLayout / BlankLayout）自行持有 <RouterView/> 出口。
  -->
  <component :is="layout" :key="$route.path" />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DashboardLayout from '@/layouts/DashboardLayout.vue'
import BlankLayout from '@/layouts/BlankLayout.vue'

const route = useRoute()
const layout = computed(() => {
  return route.meta?.layout === 'blank' ? BlankLayout : DashboardLayout
})
</script>
