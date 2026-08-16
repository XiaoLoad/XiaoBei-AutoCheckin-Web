// 路由配置：后台管理框架 + 角色权限守卫
// 拆分为「常量路由」（登录/注册/404，始终挂载）与「动态路由」（需鉴权、按角色挂载）。
// 动态路由不再一次性全量挂载：登录后仅挂载当前角色可见的路由，
// 普通用户根本不会拥有管理员路由的实例，而非仅靠守卫拦截。
import { createRouter, createWebHistory } from 'vue-router'
import { ref } from 'vue'
import { useAuthStore } from '@/store/modules/auth'
import { toast } from '@/utils/toast'

// ============ 动态路由：均需要鉴权，并按 meta.roles 做角色过滤 ============
// meta.group：侧边栏分组；meta.icon：图标名；meta.navTitle：可选，覆盖默认标题
const dynamicRoutes = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { title: '概览', requiresAuth: true, roles: ['admin', 'user'], group: '概览', icon: 'dashboard' }
  },
  {
    path: '/sign-records',
    name: 'sign-records',
    component: () => import('@/views/SignRecordsView.vue'),
    // [权限判断] 签到记录为平台用户（普通用户）专属页面：管理员无 B 平台账号，无需该页
    meta: { title: '签到记录', requiresAuth: true, roles: ['user'], group: '运营管理', icon: 'calendar', order: 1 }
  },
  {
    path: '/sign-config',
    name: 'sign-config',
    component: () => import('@/views/SignConfigView.vue'),
    meta: { title: '签到配置', requiresAuth: true, roles: ['admin', 'user'], group: '运营管理', icon: 'sliders', order: 2 }
  },
  {
    path: '/accounts',
    name: 'accounts',
    component: () => import('@/views/AccountManagementView.vue'),
    meta: { title: '账号管理', requiresAuth: true, roles: ['user'], group: '运营管理', icon: 'authorize', order: 3 }
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('@/views/UserManagementView.vue'),
    // [权限判断] 用户管理（含权限管理）仅管理员可访问；排序置于平台资源池上方
    meta: { title: '用户管理', requiresAuth: true, roles: ['admin'], group: '运营管理', icon: 'users', order: 1 }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { title: '系统设置', requiresAuth: true, roles: ['admin', 'user'], group: '系统', icon: 'settings' }
  }
]

// ============ 常量路由：始终挂载，不依赖登录态 ============
const constantRoutes = [
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
  routes: constantRoutes
})

// 动态路由是否已挂载（按角色仅挂载一次，登出时复位）
const dynamicAdded = ref(false)

// 角色是否满足路由的 roles 约束；无 roles 视为不限制。
// 注意：不再为 admin 做全局绕过——管理员只应看到/进入「roles 含 admin」的路由，
// 普通用户专属功能（如 /accounts）对管理员不可见、不可进入，与 canAccess 口径一致。
function hasRole(role, roles) {
  if (!roles || !roles.length) return true
  return roles.includes(role)
}

// 全量动态路由名册：用于「已登录用户访问了未挂载的管理员路由」这类
// 路由根本不存在（解析为 not-found）的场景，仍能识别「这是某条已知动态路由
// 但当前角色无权访问」，从而给出「无权限」提示而非静默跳仪表盘或误跳登录。
const dynamicRouteRegistry = dynamicRoutes.map((r) => ({
  path: r.path,
  roles: r.meta?.roles || []
}))

function matchRegistry(path) {
  return dynamicRouteRegistry.find((r) => r.path === path)
}

// 按角色过滤动态路由树（本项目为扁平结构，递归仅为向前兼容）
function filterAsyncRoutes(routes, role) {
  const res = []
  routes.forEach((route) => {
    const tmp = { ...route }
    if (hasRole(role, tmp.meta?.roles)) {
      if (tmp.children) tmp.children = filterAsyncRoutes(tmp.children, role)
      res.push(tmp)
    }
  })
  return res
}

// 按当前角色挂载动态路由
function addRoutesByRole(role) {
  filterAsyncRoutes(dynamicRoutes, role).forEach((r) => router.addRoute(r))
}

// 卸载全部动态路由（登出时调用，保证下一账号按自身角色重新挂载）
function removeDynamicRoutes() {
  dynamicRoutes.forEach((r) => {
    if (router.hasRoute(r.name)) router.removeRoute(r.name)
  })
  dynamicAdded.value = false
}

// 路由守卫：登录校验 + 角色权限控制 + 动态路由挂载
// [权限判断] 前端仅做体验层拦截；后端敏感接口必须再次鉴权，不可信任前端。
// 可访问性决策统一收敛到 auth.canAccess，守卫不再散点读取内部状态。
router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  if (to.meta?.title) {
    document.title = `${to.meta.title} - 小北寝室自动打卡`
  }

  // 1) 未登录：若残留动态路由则卸载，并拦截非登录/注册页 → 跳登录
  if (!auth.isAuthenticated) {
    if (dynamicAdded.value) {
      removeDynamicRoutes()
      auth.bumpRouteEpoch() // 通知菜单重算
    }
    if (to.name !== 'login' && to.name !== 'register') {
      return next({ name: 'login', query: { redirect: to.fullPath } })
    }
    return next()
  }

  // 2) 已登录：首次导航按角色挂载动态路由，并重放当前目标
  if (!dynamicAdded.value) {
    addRoutesByRole(auth.role)
    dynamicAdded.value = true
    auth.bumpRouteEpoch() // 通知菜单重算
    return next({ ...to, replace: true })
  }

  // 3) 已登录但会话失效 → 清态跳登录
  if (!auth.isSessionValid()) {
    auth.clearSession()
    return next({ name: 'login', query: { redirect: to.fullPath } })
  }

  // 4) 已登录却落到 404：多为手动输入了「未挂载的管理员路由」或无效路径。
  //    已登录态下绝不再跳登录页——按名册判定后给出明确提示并回仪表盘。
  if (to.name === 'not-found') {
    const entry = matchRegistry(to.path)
    if (entry && !hasRole(auth.role, entry.roles)) {
      // 命中已知动态路由，但当前角色无权访问（如普通用户访问 /users）
      toast('无权限访问该页面', 'error')
    } else if (!entry) {
      // 完全无效的未知路径
      toast('页面不存在', 'info')
    }
    return next('/')
  }

  // 5) 角色兜底（动态路由已按角色挂载，这里仅作冗余防御）
  if (!auth.canAccess(to)) {
    toast('无权限访问该页面', 'error')
    return next('/')
  }

  // 已登录还访问登录/注册页 → 进入仪表盘
  if (to.name === 'login' || to.name === 'register') return next('/')

  next()
})

export default router
