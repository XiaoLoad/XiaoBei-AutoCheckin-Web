<template>
  <!--
    布局分发：根据路由 meta.layout 选择布局组件。给布局加 :key="$route.path"，
    同布局内切换路由（如 / → /tasks）时路径变化会强制重建布局实例，
    其内部唯一的 <RouterView/> 随之重新渲染正确的路由组件，避免「地址变了但页面不切换」。
    各布局（DashboardLayout / BlankLayout）自行持有 <RouterView/> 出口。

    渲染门控：首屏初始导航（含路由守卫鉴权/重定向）完成前不渲染任何布局，
    否则未登录直接访问受保护 URL 会先闪现 DashboardLayout 框架再被守卫跳走。
    等 router.isReady() 后，route 已是守卫处理后的最终目标（如登录页），直接渲染正确布局。
  -->
  <component :is="layout" v-if="ready" :key="$route.path" />
  <div v-else class="min-h-screen bg-surface" />
  <!-- 全局 Toast 宿主：独立于布局，路由守卫等任意位置均可触发提示 -->
  <ToastHost />
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DashboardLayout from '@/layouts/DashboardLayout.vue'
import BlankLayout from '@/layouts/BlankLayout.vue'
import ToastHost from '@/components/ToastHost.vue'

const route = useRoute()
const router = useRouter()
const ready = ref(false)

// 等待初始导航（含全局守卫鉴权/重定向）结束后才渲染，杜绝首屏布局闪烁
onMounted(() => {
  router.isReady().then(() => {
    ready.value = true
  })
})

const layout = computed(() => {
  return route.meta?.layout === 'blank' ? BlankLayout : DashboardLayout
})
</script>
