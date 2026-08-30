<template>
  <div
    ref="root"
    class="login-root flex min-h-screen w-full flex-col bg-paper lg:grid lg:grid-cols-[1.05fr_1fr]"
  >
    <!-- 左侧品牌面板：深海军蓝实色 + 日出/打卡钟母题（PC 端展示，移动端仅保留 logo 条） -->
    <aside class="brand-panel relative flex flex-col p-6 lg:min-h-screen lg:justify-between lg:p-14">
      <!-- 环境微光（仅 PC 端，避免移动端拥挤） -->
      <div class="pointer-events-none absolute inset-0 hidden overflow-hidden lg:block">
        <div class="brand-glow-a absolute -left-16 -top-16 h-72 w-72 rounded-full bg-brand/25 blur-3xl"></div>
        <div class="brand-glow-b absolute bottom-0 right-0 h-80 w-80 rounded-full bg-amber/20 blur-3xl"></div>
      </div>

      <!-- 顶部品牌标识（移动端 / PC 端均显示） -->
      <div class="brand-line relative z-10 flex items-center gap-3">
        <img
          src="@/assets/logo.png"
          alt="小北寝室自动打卡"
          class="h-10 w-10 rounded-2xl object-cover ring-1 ring-white/15"
        />
        <span class="text-base font-bold tracking-tight text-white sm:text-lg">小北寝室自动打卡</span>
      </div>

      <!-- 中心母题：日出 / 打卡钟（仅 PC 端） -->
      <div class="relative z-10 hidden flex-1 items-center justify-center py-6 lg:flex">
        <svg
          class="brand-mark h-40 w-40 sm:h-48 sm:w-48 lg:h-56 lg:w-56"
          viewBox="0 0 200 200"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <circle
            class="brand-ring"
            cx="100"
            cy="100"
            r="90"
            stroke="rgba(255,255,255,0.18)"
            stroke-width="1.5"
            stroke-dasharray="2 8"
          />
          <circle cx="100" cy="100" r="70" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" stroke-width="1" />
          <!-- 日出弧线 -->
          <path d="M46 134 A 54 54 0 0 1 154 134" stroke="#F2A65A" stroke-width="6" stroke-linecap="round" />
          <!-- 太阳 -->
          <circle class="brand-dot" cx="100" cy="44" r="7" fill="#F2A65A" />
          <!-- 对勾（自动打卡完成） -->
          <path
            class="brand-check"
            d="M80 105 L95 121 L126 82"
            stroke="#ffffff"
            stroke-width="7"
            stroke-linecap="round"
            stroke-linejoin="round"
            pathLength="1"
          />
          <circle cx="170" cy="100" r="3" fill="rgba(255,255,255,0.5)" />
          <circle cx="100" cy="170" r="3" fill="rgba(255,255,255,0.4)" />
          <circle cx="30" cy="100" r="3" fill="rgba(255,255,255,0.4)" />
        </svg>
      </div>

      <!-- 底部文案（仅 PC 端，移动端隐藏避免表单被推下） -->
      <div class="brand-line relative z-10 hidden lg:block">
        <p class="max-w-xs text-base leading-relaxed text-white/70">
          回寝室该休息就休息，打卡这种小事，交给它。
        </p>
        <ul class="mt-6 space-y-3">
          <li
            v-for="(feat, i) in features"
            :key="i"
            class="flex items-center gap-3 text-sm text-white/80"
          >
            <span class="flex h-6 w-6 items-center justify-center rounded-full bg-amber/20 text-amber">
              <svg viewBox="0 0 20 20" fill="currentColor" class="h-3.5 w-3.5">
                <path fill-rule="evenodd" d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 9.7a1 1 0 011.4-1.4l3.1 3.1 6.8-6.8a1 1 0 011.4 0z" clip-rule="evenodd" />
              </svg>
            </span>
            {{ feat }}
          </li>
        </ul>
      </div>
    </aside>

    <!-- 右侧登录表单：PC 端为纯白实色面板（表单直接落位，不再悬浮卡片）；移动端为暖纸色 + 干净白卡 -->
    <main class="flex flex-1 items-center justify-center bg-paper p-6 sm:p-10 lg:min-h-screen lg:bg-white lg:p-16">
      <div class="login-card w-full max-w-md overflow-hidden lg:overflow-visible lg:rounded-none lg:bg-transparent lg:shadow-none lg:ring-0">
        <div class="px-7 py-9 sm:px-10 sm:py-11">
          <p class="login-field text-xs font-semibold uppercase tracking-[0.22em] text-brand">
            学生寝室 · 自动打卡
          </p>
          <h1 class="login-field mt-3 text-3xl font-extrabold tracking-tight text-ink sm:text-[2rem]">
            登录后，<span class="text-brand">打卡全自动</span>
          </h1>
          <p class="login-field mt-2 text-sm leading-relaxed text-ink-muted">
            已内置平台打卡能力，授权账号后按时自动完成，你只管正常生活。
          </p>

          <form class="mt-8 space-y-5" @submit.prevent="handleLogin">
            <!-- 账号 -->
            <div class="login-field">
              <label for="account" class="mb-1.5 block text-sm font-medium text-ink-soft">账号</label>
              <input
                id="account"
                v-model="form.account"
                type="text"
                autocomplete="username"
                placeholder="请输入学号 / 手机号"
                class="login-input"
              />
            </div>

            <!-- 密码 -->
            <div class="login-field">
              <label for="password" class="mb-1.5 block text-sm font-medium text-ink-soft">密码</label>
              <div class="relative">
                <input
                  id="password"
                  v-model="form.password"
                  :type="showPassword ? 'text' : 'password'"
                  autocomplete="current-password"
                  placeholder="请输入密码"
                  class="login-input pr-16"
                />
                <button
                  type="button"
                  class="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg px-2 py-1 text-sm text-ink-muted transition hover:bg-cloud hover:text-brand focus:text-brand focus:outline-none"
                  @click="showPassword = !showPassword"
                >
                  {{ showPassword ? '隐藏' : '显示' }}
                </button>
              </div>
            </div>

            <!-- 记住我 / 忘记密码 -->
            <div class="login-field flex items-center justify-between">
              <BaseCheckbox v-model="form.remember" label="记住密码" />
              <RouterLink
                to="/forgot-password"
                class="text-sm font-medium text-brand transition hover:text-brand-dark hover:underline"
              >
                忘记密码？
              </RouterLink>
            </div>

            <!-- 登录按钮 -->
            <button
              type="submit"
              :disabled="loading"
              class="login-submit login-field mt-2 w-full rounded-xl bg-brand px-4 py-3 text-base font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark hover:shadow-xl focus:outline-none focus:ring-4 focus:ring-brand/30 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {{ loading ? '登录中…' : '登 录' }}
            </button>
          </form>

          <!-- 底部辅助文字 -->
          <p class="login-field mt-7 text-center text-sm text-ink-muted">
            还没有账号？
            <RouterLink
              to="/register"
              class="font-medium text-brand transition hover:text-brand-dark hover:underline"
            >
              立即注册
            </RouterLink>
          </p>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter, useRoute, RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useLoginAnimations } from '@/composables/useLoginAnimations'
import BaseCheckbox from '@/components/BaseCheckbox.vue'

const root = ref(null)
const loading = ref(false)
const showPassword = ref(false)

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const features = [
  '自动抓包解析平台打卡协议',
  '到点自动完成，无需手动',
  '打卡记录实时留痕回看'
]

const form = reactive({
  account: '',
  password: '',
  remember: false
})

// 初始化 GSAP 动画（自动处理挂载/销毁生命周期）
useLoginAnimations(root)

async function handleLogin() {
  if (!form.account.trim() || !form.password.trim()) {
    alert('请填写账号和密码')
    return
  }
  loading.value = true
  try {
    // 调用后端 /api/auth/login，store 内写入 token 与用户信息；
    // 目的地由路由守卫按登录角色解析（redirect 优先），无需在此读取响应
    await authStore.login({
      account: form.account.trim(),
      password: form.password
    })
    const redirect = route.query.redirect
    router.replace(typeof redirect === 'string' ? redirect : '/')
  } catch (e) {
    // 后端已返回清晰错误（账号不存在 / 密码错误 / 账号已禁用）
    alert(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>
