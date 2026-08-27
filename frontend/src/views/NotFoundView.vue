<template>
  <!-- 完全独立的全屏 404 页面：经 BlankLayout 渲染，不挂载任何应用框架（侧边栏/顶栏） -->
  <div class="min-h-screen w-full flex items-center justify-center bg-gradient-to-br from-slate-50 to-brand/5 px-4">
    <div class="w-full max-w-md text-center">
      <div class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-brand/10 text-brand">
        <!-- 问号占位图标 -->
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="9" />
          <path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3" />
          <path d="M12 17h.01" />
        </svg>
      </div>

      <p class="text-7xl font-black tracking-tight text-brand">404</p>
      <h1 class="mt-3 text-xl font-semibold text-ink">页面不存在</h1>
      <p class="mt-2 text-sm leading-relaxed text-ink-muted">
        您访问的页面不存在、已被移动，或您没有权限访问。
      </p>

      <div class="mt-8 flex flex-col items-center gap-3">
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark focus:outline-none focus:ring-4 focus:ring-brand/30"
          @click="goBack"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 12H5" />
            <path d="M12 19l-7-7 7-7" />
          </svg>
          返回上一页
        </button>

        <RouterLink
          :to="fallback"
          class="text-sm font-medium text-brand transition hover:text-brand-dark hover:underline"
        >
          返回{{ auth.isAuthenticated ? '首页' : '登录页' }}
        </RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

// 指定返回页：支持 ?redirect= 覆盖；否则按登录态回首页 / 登录页
const fallback = computed(() =>
  route.query.redirect
    ? String(route.query.redirect)
    : (auth.isAuthenticated ? '/' : '/login')
)

function goBack() {
  // 存在应用内历史则回退上一页；否则跳转到指定/默认页（避免离开站点）
  const hasAppHistory = !!(window.history.state && window.history.state.back)
  if (hasAppHistory && !route.query.redirect) {
    router.back()
  } else {
    router.replace(fallback.value)
  }
}
</script>
