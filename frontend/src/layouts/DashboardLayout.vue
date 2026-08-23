<template>
  <div class="flex h-screen overflow-hidden bg-cloud text-ink">
    <!-- 侧边栏：PC 常驻，移动端抽屉 -->
    <aside
      class="fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-ink transition-transform duration-300 lg:static lg:translate-x-0"
      :class="open ? 'translate-x-0' : '-translate-x-full'"
    >
      <!-- 品牌区 -->
      <div class="flex items-center gap-3 h-16 px-5 border-b border-white/10">
        <img
          src="@/assets/logo.png"
          alt="小北寝室自动打卡"
          class="h-10 w-10 shrink-0 rounded-2xl object-cover ring-1 ring-white/15"
        />
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
      <!-- 顶栏：两端对齐（justify-between）。左侧为移动端菜单按钮 + 标题，
           右侧为消息图标 + 管理员头像；已移除搜索框元素。 -->
      <header class="sticky top-0 z-20 flex items-center justify-between h-16 px-4 sm:px-6 bg-white/80 backdrop-blur border-b border-ink/5">
        <!-- 左侧：移动端菜单按钮 + 标题 -->
        <div class="flex items-center gap-3 min-w-0">
          <button class="lg:hidden grid place-items-center w-9 h-9 rounded-lg hover:bg-cloud text-ink-muted shrink-0" @click="open = true" aria-label="打开菜单">
            <Icon name="menu" :size="20" />
          </button>
          <h1 class="text-base sm:text-lg font-semibold text-ink truncate">{{ pageTitle }}</h1>
        </div>

        <!-- 右侧：消息图标 + 管理员头像 -->
        <div class="flex items-center gap-3 shrink-0">
          <button class="relative grid place-items-center w-9 h-9 rounded-lg hover:bg-cloud text-ink-muted" aria-label="通知">
            <Icon name="bell" :size="20" />
            <span class="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-danger ring-2 ring-white" />
          </button>
          <!-- [权限判断] 顶栏角色头像：按登录角色动态显示首字（管理员→管 / 普通用户→普），悬停提示完整角色 -->
          <span
            class="hidden sm:grid place-items-center w-9 h-9 rounded-full bg-brand/15 text-brand font-semibold text-sm"
            :title="roleLabel"
          >{{ roleLabel.charAt(0) }}</span>
        </div>
      </header>

      <!-- 内容：布局自行持有唯一 RouterView 出口；App 已按 $route.path 为布局加 key，
           切换路由时布局重建、此处随之渲染正确的路由组件。 -->
      <!-- 内容滚动容器：保留 flex 列布局，使各页面根容器（flex-1）的高度分配与改动前一致，
           用户/账号管理等页的列表卡片固定高度与内部滚动不受影响。
           底部间距收归各页面根容器末尾的真实占位块（非滚动容器自身 padding，滚动时不被折叠），全站统一 24px。 -->
      <main class="flex-1 flex flex-col overflow-y-auto p-4 sm:px-6 sm:pt-6 content-scroll">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter, RouterLink, RouterView } from 'vue-router'
import { useAuthStore } from '@/store/modules/auth'
import { hasRole } from '@/directives/permission'
import Icon from '@/components/Icon.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'

const route = useRoute()
const router = useRouter()
const open = ref(false)
const auth = useAuthStore()
// 顶栏标题：默认取路由 meta.title；签到配置页按角色区分（管理员维护平台资源池）
const pageTitle = computed(() => {
  if (route.path === '/sign-config') return auth.isAdmin ? '平台资源池' : '签到配置'
  return route.meta?.title || '概览'
})

// 退出登录二次确认弹窗状态
const showLogoutConfirm = ref(false)

// [权限判断] 按角色渲染菜单：管理员可见全部；普通用户仅见本人相关与"个人设置"
const roleLabel = computed(() => (auth.isAdmin ? '管理员' : '普通用户'))

// 菜单由「已挂载的路由」按角色派生，而非硬编码分组：
// 动态路由登录后才按角色挂载，故普通用户根本不会拥有管理员路由，菜单天然收敛。
// 依赖 auth.routeEpoch：动态路由挂载/卸载后强制重算菜单。
const navGroups = computed(() => {
  // 依赖 auth.routeEpoch：动态路由挂载/卸载后该值自增，强制本 computed 重算菜单
  auth.routeEpoch

  const order = []
  const map = {}
  router
    .getRoutes()
    .filter((r) => r.meta?.requiresAuth && hasRole(auth.role, r.meta.roles))
    .forEach((r) => {
      const g = r.meta.group || '其它'
      if (!map[g]) {
        map[g] = []
        order.push(g)
      }
      map[g].push({ name: navTitleOf(r), to: r.path, icon: r.meta.icon, order: r.meta.order ?? 99 })
    })
  // 同组导航按 meta.order 升序排列（未声明者置后），保证顺序确定、不依赖路由注册顺序
  return order.map((g) => ({ title: g, items: map[g].slice().sort((a, b) => a.order - b.order) }))
})

// 个别路由按角色使用不同的菜单文案（其余沿用 meta.title）
function navTitleOf(r) {
  if (r.name === 'sign-config') return auth.isAdmin ? '平台资源池' : '签到配置'
  if (r.name === 'settings') return auth.isAdmin ? '系统设置' : '个人设置'
  return r.meta?.title || r.name
}

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
