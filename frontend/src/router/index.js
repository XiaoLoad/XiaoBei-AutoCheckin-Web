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
    path: '/tasks',
    name: 'tasks',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { title: '打卡任务', requiresAuth: true, roles: ['admin', 'user'] }
  },
  {
    path: '/records',
    name: 'records',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { title: '打卡记录', requiresAuth: true, roles: ['admin', 'user'] }
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
// [权限判断] 前端仅做体验层拦截；后端敏感接口必须再次鉴权，不可信任前端
router.beforeEach((to, from, next) => {
  if (to.meta?.title) {
    document.title = `${to.meta.title} - 小北寝室自动打卡`
  }
  const auth = useAuthStore()

  // 会话是否有效 = 本地存在 token 且未过期（比对 JWT exp）。
  // 仅判断 isAuthenticated 会在 token 过期时先放行、等接口 401 才跳转，
  // 造成"先渲染受保护页框架再跳登录"的闪烁，故此处一并校验有效性。
  const valid = auth.isAuthenticated && auth.isSessionValid()

  // 需要登录的页面
  if (to.meta?.requiresAuth) {
    if (!valid) {
      // 清理已失效的本地会话，避免后续请求带着无效 token 空跑
      if (auth.isAuthenticated) auth.clearSession()
      return next({ name: 'login', query: { redirect: to.fullPath } })
    }
    // 角色不匹配（如普通用户访问管理员专属页面）→ 回到自己的仪表盘
    const roles = to.meta?.roles
    if (roles && !roles.includes(auth.role)) {
      return next('/')
    }
  }

  // 已登录还访问登录页/注册页 → 直接进入仪表盘
  if ((to.name === 'login' || to.name === 'register') && valid) {
    return next('/')
  }

  next()
})

export default router
