<template>
  <div class="flex h-screen overflow-hidden bg-cloud text-ink">
    <!-- 侧边栏：PC 常驻，移动端抽屉 -->
    <aside
      class="fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-ink transition-transform duration-300 lg:static lg:translate-x-0"
      :class="open ? 'translate-x-0' : '-translate-x-full'"
    >
      <!-- 品牌区 -->
      <div class="flex items-center gap-3 h-16 px-5 border-b border-white/10">
        <span class="grid place-items-center w-9 h-9 rounded-xl bg-brand text-white shadow-lg shadow-brand/30">
          <svg viewBox="0 0 24 24" class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
        </span>
        <div class="leading-tight">
          <p class="text-sm font-semibold text-white">小北寝室打卡</p>
          <p class="text-[11px] text-white/50">管理控制台</p>
        </div>
      </div>

      <!-- 导航 -->
      <nav class="flex-1 overflow-y-auto px-3 py-4 space-y-6 sidebar-scroll">
        <div v-for="group in navGroups" :key="group.title">
          <p class="px-3 mb-2 text-[11px] font-semibold uppercase tracking-wider text-white/35">
            {{ group.title }}
          </p>
          <div class="space-y-1">
            <RouterLink
              v-for="item in group.items"
              :key="item.to"
              :to="item.to"
              exact-active-class="nav-link--active"
              active-class="nav-link--active"
              class="nav-link"
              @click="open = false"
            >
              <Icon :name="item.icon" :size="19" />
              <span>{{ item.name }}</span>
            </RouterLink>
          </div>
        </div>
      </nav>

      <!-- 用户区 -->
      <div class="border-t border-white/10 p-3">
        <div class="flex items-center gap-3 rounded-xl px-2 py-2 hover:bg-white/5 transition-colors">
          <span class="grid place-items-center w-9 h-9 rounded-full bg-brand/20 text-brand font-semibold">
            {{ (auth.username || 'U').charAt(0).toUpperCase() }}
          </span>
          <div class="leading-tight flex-1 min-w-0">
            <p class="text-sm font-medium text-white truncate">{{ auth.username || '未登录' }}</p>
            <p class="text-[11px] text-white/45 truncate">{{ roleLabel }}</p>
          </div>
          <button
            class="grid place-items-center w-8 h-8 rounded-lg hover:bg-white/10 text-white/40 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            :disabled="auth.loggingOut"
            aria-label="退出登录"
            @click="handleLogout"
          >
            <Icon v-if="!auth.loggingOut" name="logout" :size="18" />
            <span v-else class="block w-4 h-4 rounded-full border-2 border-white/40 border-t-white animate-spin" />
          </button>
        </div>
      </div>
    </aside>

    <!-- 移动端遮罩 -->
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-30 bg-ink/40 lg:hidden" @click="open = false" />
    </Transition>

    <!-- 退出登录二次确认弹窗（通用组件，可复用于其它危险操作） -->
    <ConfirmModal
      v-model="showLogoutConfirm"
      title="退出登录"
      message="确定要退出当前账号吗？退出后需要重新登录才能继续使用。"
      icon="logout"
      confirm-text="退出登录"
      cancel-text="取消"
      danger
      :confirming="auth.loggingOut"
      @confirm="confirmLogout"
      @cancel="cancelLogout"
    />

    <!-- 主区域 -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- 顶栏 -->
      <header class="sticky top-0 z-20 flex items-center gap-3 h-16 px-4 sm:px-6 bg-white/80 backdrop-blur border-b border-ink/5">
        <button class="lg:hidden grid place-items-center w-9 h-9 rounded-lg hover:bg-cloud text-ink-muted" @click="open = true" aria-label="打开菜单">
          <Icon name="menu" :size="20" />
        </button>
        <h1 class="text-base sm:text-lg font-semibold text-ink">{{ pageTitle }}</h1>

        <div class="hidden md:flex items-center gap-2 ml-4 flex-1 max-w-md">
          <div class="relative w-full">
            <Icon name="search" :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
            <input
              type="text"
              placeholder="搜索成员、任务或记录…"
              class="w-full rounded-xl border border-ink/10 bg-cloud/60 pl-9 pr-3 py-2 text-sm text-ink placeholder:text-ink-muted/70 focus:border-brand focus:bg-white focus:outline-none focus:ring-4 focus:ring-brand/10"
            />
          </div>
        </div>

        <div class="flex-1 md:flex-none" />
        <button class="relative grid place-items-center w-9 h-9 rounded-lg hover:bg-cloud text-ink-muted" aria-label="通知">
          <Icon name="bell" :size="20" />
          <span class="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-danger ring-2 ring-white" />
        </button>
        <span class="hidden sm:grid place-items-center w-9 h-9 rounded-full bg-brand/15 text-brand font-semibold text-sm">管</span>
      </header>

      <!-- 内容：布局自行持有唯一 RouterView 出口；App 已按 $route.path 为布局加 key，
           切换路由时布局重建、此处随之渲染正确的路由组件。 -->
      <main class="flex-1 overflow-y-auto p-4 sm:p-6 content-scroll">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter, RouterLink, RouterView } from 'vue-router'
import { useAuthStore } from '@/store/modules/auth'
import Icon from '@/components/Icon.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'

const route = useRoute()
const router = useRouter()
const open = ref(false)
const auth = useAuthStore()
const pageTitle = computed(() => route.meta?.title || '概览')

// 退出登录二次确认弹窗状态
const showLogoutConfirm = ref(false)

// [权限判断] 按角色渲染菜单：管理员可见全部；普通用户仅见本人相关与"个人设置"
const roleLabel = computed(() => (auth.isAdmin ? '管理员' : '普通用户'))

const navGroups = computed(() => {
  const groups = [
    { title: '概览', items: [{ name: '概览', to: '/', icon: 'dashboard' }] },
    {
      title: '运营管理',
      items: [
        { name: '打卡任务', to: '/tasks', icon: 'tasks' },
        { name: '打卡记录', to: '/records', icon: 'records' },
        { name: '账号授权', to: '/accounts', icon: 'authorize' }
      ]
    }
  ]
  if (auth.isAdmin) {
    groups.push({
      title: '系统',
      items: [
        { name: '寝室成员', to: '/members', icon: 'members' },
        { name: '系统设置', to: '/settings', icon: 'settings' }
      ]
    })
  } else {
    groups.push({
      title: '系统',
      items: [{ name: '个人设置', to: '/settings', icon: 'settings' }]
    })
  }
  return groups
})

// 点击退出按钮：先弹二次确认，不直接登出
function handleLogout() {
  showLogoutConfirm.value = true
}

// 弹窗确认：清理会话（服务端吊销 + 本地清除 + 兜底），再跳转登录页
async function confirmLogout() {
  try {
    await auth.logout()
  } finally {
    showLogoutConfirm.value = false
    router.replace('/login')
  }
}

function cancelLogout() {
  showLogoutConfirm.value = false
}
</script>

<style scoped>
.nav-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  border-radius: 0.75rem;
  padding: 0.625rem 0.75rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
  transition: background-color 0.15s, color 0.15s;
}
.nav-link:hover {
  background-color: rgba(255, 255, 255, 0.06);
  color: #fff;
}
.nav-link--active {
  background-color: rgba(255, 255, 255, 0.1);
  color: #fff;
  box-shadow: inset 3px 0 0 0 #1674f8;
}
.sidebar-scroll::-webkit-scrollbar,
.content-scroll::-webkit-scrollbar { width: 6px; }
.sidebar-scroll::-webkit-scrollbar-thumb,
.content-scroll::-webkit-scrollbar-thumb { background: rgba(20, 33, 61, 0.12); border-radius: 9999px; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
