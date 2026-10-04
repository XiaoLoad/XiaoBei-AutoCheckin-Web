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
    <main class="flex flex-1 items-center justify-center bg-paper p-6 sm:p-10 lg:min-h-screen lg:bg-elevated lg:p-16">
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

          <form ref="formRef" class="mt-8 space-y-5" @submit.prevent="handleLogin">
            <!-- 登录失败横幅的常驻容器：显式 height:0 + overflow hidden，无错误时不占任何布局空间。
                 展开由 GSAP 动画 height:auto 实现——从 0 平滑过渡到自然高度，
                 下方元素被逐渐推开而非瞬间跳位，消除 v-if 插拔导致的布局抖动。 -->
            <div ref="bannerWrap" class="h-0 overflow-hidden">
              <div
                class="login-error-banner flex items-start gap-2.5 rounded-xl border border-danger/25 bg-danger/10 px-3.5 py-2.5"
                role="alert"
              >
                <Icon name="alert" :size="16" class="mt-0.5 shrink-0 text-danger" />
                <p class="text-sm leading-relaxed text-danger">{{ formError }}</p>
              </div>
            </div>

            <!-- 账号 -->
            <div class="login-field">
              <label for="account" class="mb-1.5 block text-sm font-medium text-ink-soft">账号</label>
              <div class="relative">
                <input
                  id="account"
                  ref="accountInput"
                  v-model="form.account"
                  type="text"
                  autocomplete="username"
                  placeholder="请输入学号 / 手机号"
                  class="login-input pr-11"
                  :class="{ 'login-input-invalid': fieldErrors.account || credInvalid }"
                  @input="clearFieldError('account')"
                />
                <!-- 一键清除：右侧内边距常驻（不随按钮显隐变化），
                     否则首个字符一敲、按钮冒出来的同时文字会被挤着横跳一下。
                     mousedown.prevent 让输入框在点按钮时不失焦：既省掉一次 blur→focus 的
                     字段上下浮动，也避免焦点被抢走后再交还。 -->
                <button
                  v-if="form.account"
                  type="button"
                  tabindex="-1"
                  class="login-clear right-3"
                  aria-label="清除账号"
                  @mousedown.prevent
                  @click="clearField('account')"
                >
                  <Icon name="close" :size="13" :stroke-width="2.4" />
                </button>
              </div>
              <p v-if="fieldErrors.account" class="mt-1.5 text-xs font-medium text-danger">
                {{ fieldErrors.account }}
              </p>
            </div>

            <!-- 密码 -->
            <div class="login-field">
              <label for="password" class="mb-1.5 block text-sm font-medium text-ink-soft">密码</label>
              <div class="relative">
                <input
                  id="password"
                  ref="passwordInput"
                  v-model="form.password"
                  :type="showPassword ? 'text' : 'password'"
                  autocomplete="current-password"
                  placeholder="请输入密码"
                  class="login-input pwd-input pr-[5.75rem]"
                  :class="{ 'login-input-invalid': fieldErrors.password || credInvalid }"
                  @input="clearFieldError('password')"
                />
                <!-- 清除钮排在「显示 / 隐藏」左侧，与它留 4px 间隔；两者共占右侧 5.75rem -->
                <button
                  v-if="form.password"
                  type="button"
                  tabindex="-1"
                  class="login-clear right-[3.75rem]"
                  aria-label="清除密码"
                  @mousedown.prevent
                  @click="clearField('password')"
                >
                  <Icon name="close" :size="13" :stroke-width="2.4" />
                </button>
                <button
                  type="button"
                  class="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg px-2 py-1 text-sm text-ink-muted transition hover:bg-cloud hover:text-brand focus:text-brand focus:outline-none"
                  @click="showPassword = !showPassword"
                >
                  {{ showPassword ? '隐藏' : '显示' }}
                </button>
              </div>
              <p v-if="fieldErrors.password" class="mt-1.5 text-xs font-medium text-danger">
                {{ fieldErrors.password }}
              </p>
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

            <!-- 登录按钮：过渡只留 background-color / box-shadow。
                 用 Tailwind 的 transition（默认含 opacity 与 transform）会和 GSAP 抢同一批属性：
                 GSAP 每帧写一个值，浏览器再按 150ms 曲线把它拖过去，入场与 hover 缩放都被拉慢失真。 -->
            <button
              type="submit"
              :disabled="loading"
              class="login-submit login-field mt-2 w-full rounded-xl bg-brand px-4 py-3 text-base font-semibold text-white shadow-lg shadow-brand/25 transition-[background-color,box-shadow] hover:bg-brand-dark hover:shadow-xl focus:outline-none focus:ring-4 focus:ring-brand/30 disabled:cursor-not-allowed disabled:opacity-60"
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
import { gsap } from 'gsap'
import { useAuthStore } from '@/stores/auth'
import { useLoginAnimations } from '@/composables/useLoginAnimations'
import BaseCheckbox from '@/components/BaseCheckbox.vue'
import Icon from '@/components/Icon.vue'

const root = ref(null)
const formRef = ref(null)
const loading = ref(false)
const showPassword = ref(false)
const accountInput = ref(null)
const passwordInput = ref(null)

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

// 一键清除：清空后把焦点交还输入框，省去再点一次才能接着输入
function clearField(key) {
  form[key] = ''
  clearFieldError(key)
  const el = key === 'account' ? accountInput.value : passwordInput.value
  el?.focus()
}

// 提示体系（无模态）：字段级错误内联在输入框下、登录失败以表单顶部横幅常驻。
// 横幅不自动消失——失败原因需要时间读，重新输入时自动清除（clearFieldError）。
const fieldErrors = reactive({ account: '', password: '' })
// 凭据类失败的红边标记：无内联文字（原因已在横幅说明），只给两个输入框描红边
const credInvalid = ref(false)
// 登录失败横幅文案（表单顶部，常驻至重新输入时清除）
const formError = ref('')
// 横幅常驻容器：GSAP 用它在 0 ↔ auto 高度间平滑展开/收起（避免 v-if 插拔抖动）
const bannerWrap = ref(null)

function clearFieldError(key) {
  fieldErrors[key] = ''
  credInvalid.value = false
  // 横幅收起：高度补回 0 并淡出，下方内容平滑回流（无 v-if 插拔的瞬间跳动）
  if (formError.value) {
    formError.value = ''
    gsap.to(bannerWrap.value, {
      height: 0,
      duration: 0.3,
      ease: 'power2.inOut',
      overwrite: 'auto'
    })
  }
}

// 横幅展开入场：先在常驻容器上做 0→auto 高度动画（下方元素被平滑推开，消除重排跳位），
// 横幅本体再做「下移 10px + 95% 缩放 + 淡入」的品牌向入场——transform/opacity 走合成器，
// 不触发重排；power3.out 前快后缓，与登录页其余 GSAP 入场同一节奏语言。
// reduced-motion 用户跳过全部动画：高度直接到位、无位移淡入，静态呈现。
const REDUCED_MOTION =
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

function expandBanner() {
  const wrap = bannerWrap.value
  const banner = wrap?.querySelector('.login-error-banner')
  if (!wrap || !banner) return

  if (REDUCED_MOTION) {
    gsap.set(wrap, { height: 'auto' })
    return
  }

  // 先铺初值（横幅本体的位移/缩放/透明），容器高度随后动画到自然高度；
  // height: 'auto' 由 GSAP 在补间开始瞬间量取目标高度，期间下方内容的推移完全连续
  gsap.set(banner, { y: -10, scale: 0.97, autoAlpha: 0 })
  gsap.to(wrap, {
    height: 'auto',
    duration: 0.38,
    ease: 'power3.out',
    overwrite: 'auto'
  })
  gsap.to(banner, {
    y: 0,
    scale: 1,
    autoAlpha: 1,
    duration: 0.42,
    ease: 'power3.out',
    overwrite: 'auto'
  })
}

// 横幅强调动画：入场展开落定后的轻微左右摇摆（幅度仅 ±4px，纯 transform），
// overwrite:'auto' 防止与进行中的入场补间互相拉扯；reduced-motion 用户跳过。
function shakeBanner() {
  if (REDUCED_MOTION) return
  const banner = bannerWrap.value?.querySelector('.login-error-banner')
  banner &&
    gsap.to(banner, {
      keyframes: { x: [-4, 4, -2, 2, 0] },
      duration: 0.38,
      delay: 0.3,
      ease: 'power1.inOut',
      overwrite: 'auto'
    })
}

// 初始化 GSAP 动画（自动处理挂载/销毁生命周期）
useLoginAnimations(root)

async function handleLogin() {
  // 提交前校验：空字段直接内联标注，不再弹窗打断
  fieldErrors.account = form.account.trim() ? '' : '请输入账号'
  fieldErrors.password = form.password ? '' : '请输入密码'
  if (fieldErrors.account || fieldErrors.password) return

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
    // 后端已返回清晰错误（账号或密码错误 / 账号已被禁用 / 尝试过于频繁）
    formError.value = e.message || '登录失败，请稍后重试'
    // 凭据类失败（1001）同时描红两个输入框，指明出错的就是这两个字段；
    // 禁用（1003）/限频（1004）与字段无关，仅横幅提示
    if (e.bizCode === undefined || e.bizCode === 1001 || e.bizCode === 1002) {
      credInvalid.value = true
    }
    expandBanner()
    shakeBanner()
  } finally {
    loading.value = false
  }
}
</script>
