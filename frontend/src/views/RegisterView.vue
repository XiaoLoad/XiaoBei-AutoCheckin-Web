<template>
  <!-- 独立全屏注册页：与登录页同为 blank 布局，不挂载应用框架（侧边栏/顶栏） -->
  <div class="min-h-screen w-full flex items-center justify-center bg-gradient-to-br from-surface to-brand/5 px-4">
    <div class="w-full max-w-md text-center">
      <div class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-brand/10 text-brand">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M20 8v6" />
          <path d="M23 11h-6" />
        </svg>
      </div>

      <h1 class="text-2xl font-bold text-ink">注册账号</h1>
      <p class="mt-3 text-sm leading-relaxed text-ink-muted">
        本系统采用寝室管理员统一开通账号机制，暂不支持自助注册。<br />
        如需使用，请联系你的寝室管理员获取账号后登录。
      </p>

      <div class="mt-8 flex flex-col items-center gap-3">
        <RouterLink
          to="/login"
          class="inline-flex items-center gap-2 rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark focus:outline-none focus:ring-4 focus:ring-brand/30"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 12H5" />
            <path d="M12 19l-7-7 7-7" />
          </svg>
          返回登录
        </RouterLink>

        <button
          type="button"
          class="text-sm font-medium text-brand transition hover:text-brand-dark hover:underline"
          @click="goBack"
        >
          返回上一页
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

function goBack() {
  const hasAppHistory = !!(window.history.state && window.history.state.back)
  if (hasAppHistory) {
    router.back()
  } else {
    router.replace('/login')
  }
}
</script>
