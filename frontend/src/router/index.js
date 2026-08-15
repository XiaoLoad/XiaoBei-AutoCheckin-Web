// 路由配置：后台管理框架 + 角色权限守卫
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store/modules/auth'

// 路由懒加载，按功能模块组织
const routes = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { title: '概览', requiresAuth: true, roles: ['admin', 'user'] }
  },
  {
    path: '/sign-records',
    name: 'sign-records',
    component: () => import('@/views/SignRecordsView.vue'),
    meta: { title: '签到记录', requiresAuth: true, roles: ['admin', 'user'] }
  },
  {
    path: '/sign-config',
    name: 'sign-config',
    component: () => import('@/views/SignConfigView.vue'),
    meta: { title: '签到配置', requiresAuth: true, roles: ['admin', 'user'] }
  },
  {
    path: '/accounts',
    name: 'accounts',
    component: () => import('@/views/AccountManagementView.vue'),
    meta: { title: '账号管理', requiresAuth: true, roles: ['admin', 'user'] }
  },
  {
    path: '/members',
    name: 'members',
    component: () => import('@/views/PlaceholderView.vue'),
    // [权限判断] 仅管理员可访问寝室成员管理
    meta: { title: '寝室成员', requiresAuth: true, roles: ['admin'] }
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('@/views/UserManagementView.vue'),
    // [权限判断] 用户管理（含权限管理）仅管理员可访问
    meta: { title: '用户管理', requiresAuth: true, roles: ['admin'] }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { title: '系统设置', requiresAuth: true, roles: ['admin', 'user'] }
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', layout: 'blank' }
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    // 注册页与登录页同为独立全屏页，不挂载应用框架（侧边栏/顶栏）
    meta: { title: '注册', layout: 'blank' }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    // [布局] 404 必须是完全独立的全屏页，不渲染任何应用框架组件
    meta: { title: '页面不存在', layout: 'blank' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：登录校验 + 角色权限控制
// [权限判断] 前端仅做体验层拦截；后端敏感接口必须再次鉴权，不可信任前端。
// 可访问性决策统一收敛到 auth.canAccess，守卫不再散点读取内部状态。
router.beforeEach((to, from, next) => {
  if (to.meta?.title) {
    document.title = `${to.meta.title} - 小北寝室自动打卡`
  }
  const auth = useAuthStore()

  // 用统一的 canAccess 入口决策；不可访问时按「未登录 / 会话过期 / 角色不符」分流
  if (!auth.canAccess(to)) {
    const meta = to.meta || {}
    if (meta.requiresAuth && !auth.isAuthenticated) {
      // 未登录 → 跳转登录页（携带 redirect）
      return next({ name: 'login', query: { redirect: to.fullPath } })
    }
    if (auth.isAuthenticated && !auth.isSessionValid()) {
      // 已登录但会话过期 → 清理本地态后跳转登录页
      auth.clearSession()
      return next({ name: 'login', query: { redirect: to.fullPath } })
    }
    // 已登录且有效，但角色不匹配 → 回到自己的仪表盘
    return next('/')
  }

  // 已登录还访问登录页/注册页 → 直接进入仪表盘
  if ((to.name === 'login' || to.name === 'register') && auth.isAuthenticated && auth.isSessionValid()) {
    return next('/')
  }

  next()
})

export default router
