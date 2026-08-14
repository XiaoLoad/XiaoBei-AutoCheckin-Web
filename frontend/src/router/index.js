// 路由配置：按功能模块划分（后台管理框架）
import { createRouter, createWebHistory } from 'vue-router'

// 路由懒加载，按功能模块组织
const routes = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { title: '概览' }
  },
  {
    path: '/tasks',
    name: 'tasks',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { title: '打卡任务' }
  },
  {
    path: '/records',
    name: 'records',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { title: '打卡记录' }
  },
  {
    path: '/accounts',
    name: 'accounts',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { title: '账号授权' }
  },
  {
    path: '/members',
    name: 'members',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { title: '寝室成员' }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { title: '系统设置' }
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', layout: 'blank' }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '页面不存在' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：可在此做登录校验、页面标题设置等
router.beforeEach((to, from, next) => {
  if (to.meta?.title) {
    document.title = `${to.meta.title} - 小北寝室自动打卡`
  }
  next()
})

export default router
