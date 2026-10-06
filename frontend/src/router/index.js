// 路由配置：后台管理框架 + 角色权限守卫
// 拆分为「常量路由」（登录/注册/404，始终挂载）与「动态路由」（需鉴权、按角色挂载）。
// 动态路由不再一次性全量挂载：登录后仅挂载当前角色可见的路由，
// 普通用户根本不会拥有管理员路由的实例，而非仅靠守卫拦截。
import { createRouter, createWebHistory } from 'vue-router'
import { ref } from 'vue'
import { useAuthStore, decodeJwt } from '@/stores/auth'
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
    meta: { title: '签到记录', requiresAuth: true, roles: ['user'], group: '运营管理', icon: 'calendar', order: 2 }
  },
  {
    path: '/sign-config',
    name: 'sign-config',
    component: () => import('@/views/SignConfigView.vue'),
    meta: { title: '签到配置', requiresAuth: true, roles: ['admin', 'user'], group: '运营管理', icon: 'sliders', order: 3 }
  },
  {
    path: '/accounts',
    name: 'accounts',
    component: () => import('@/views/AccountManagementView.vue'),
    meta: { title: '账号管理', requiresAuth: true, roles: ['user'], group: '运营管理', icon: 'authorize', order: 1 }
  },
  {
    path: '/schedules',
    name: 'schedules',
    component: () => import('@/views/SchedulesView.vue'),
    // [权限判断] 定时任务为平台用户（普通用户）专属页面：管理员无 B 平台账号，无需该页
    meta: { title: '定时任务', requiresAuth: true, roles: ['user'], group: '运营管理', icon: 'clock', order: 4 }
  },
  {
    path: '/task-logs',
    name: 'task-logs',
    component: () => import('@/views/TaskLogsView.vue'),
    // 任务日志：平台用户（普通用户）专属页面，暂为占位实现
    meta: { title: '任务日志', requiresAuth: true, roles: ['user'], group: '运营管理', icon: 'records', order: 5 }
  },
  {
    path: '/group-push',
    name: 'group-push',
    component: () => import('@/views/GroupPushView.vue'),
    // 分组：班级（className 派生）/ 寝室（手动成员）两类分组，承载图库归属与 QQ 群合并推送
    meta: { title: '分组', requiresAuth: true, roles: ['user'], group: '运营管理', icon: 'send', order: 6 }
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('@/views/UserManagementView.vue'),
    // [权限判断] 用户管理（含权限管理）仅管理员可访问；order 0 使其始终排在运营管理分组最前（普通用户不可见，仅影响管理员视图）
    meta: { title: '用户管理', requiresAuth: true, roles: ['admin'], group: '运营管理', icon: 'users', order: 0 }
  },
  {
    path: '/site-records',
    name: 'site-records',
    component: () => import('@/views/SiteRecordsView.vue'),
    // [权限判断] 全站签到记录仅管理员可访问：账号树巡检所有站点用户的 B 平台账号及其历史签到
    meta: { title: '全站签到记录', requiresAuth: true, roles: ['admin'], group: '运营管理', icon: 'records', order: 1 }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SystemSettingsView.vue'),
    // [权限判断] 账户安全对所有角色开放；系统参数/系统信息区仅管理员可见（页面内按角色分区，后端二次校验）
    meta: { title: '系统设置', requiresAuth: true, roles: ['admin', 'user'], group: '系统', icon: 'settings' }
  },
  {
    path: '/user-logs',
    name: 'user-logs',
    component: () => import('@/views/UserLogsView.vue'),
    // [权限判断] 用户日志（平台操作审计）仅管理员可访问：含全员用户名、IP、UA 与权限变更明细
    meta: { title: '用户日志', requiresAuth: true, roles: ['admin'], group: '运营管理', icon: 'shield', order: 2 }
  },
  {
    path: '/runtime-logs',
    name: 'runtime-logs',
    component: () => import('@/views/RuntimeLogsView.vue'),
    // [权限判断] 运行日志仅管理员可访问：服务端 app.log 只读尾部（调度/推送过程排障）
    meta: { title: '运行日志', requiresAuth: true, roles: ['admin'], group: '系统', icon: 'records' }
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
// 刷新竞态兜底：记录已为哪个 path 补挂并重放过，防止「未挂载→补挂→仍 not-found→再补挂」死循环
const replayAttempted = ref('')

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

// 解析当前角色：优先用 store 中已挂载的 user.role；
// 兜底：localStorage 的 user 缺失（极少见）时，从 JWT payload 的 role 字段补回，
// 避免「role 为空 → 动态路由全部不加 → 刷新落到 not-found → 回仪表盘」的死局。
function resolveRole() {
  const auth = useAuthStore()
  if (auth.role) return auth.role
  try {
    const json = auth.token ? decodeJwt(auth.token) : null
    if (json?.role) return json.role
  } catch {
    /* 解析失败忽略，回落到空角色 */
  }
  return ''
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
  replayAttempted.value = ''
}

// 应用启动时为已登录会话预注册动态路由：刷新后首跳不再因「路由尚未挂载」而落到
// 404 → 仪表盘，浏览器地址栏的当前页能被直接解析并停留。须在 pinia 安装后调用。
// 用 try/catch 包裹：预注册失败不得阻塞应用启动，守卫会在首次导航时兜底补挂。
export function syncInitialRoutes() {
  try {
    const auth = useAuthStore()
    if (auth.isAuthenticated && auth.isSessionValid() && !dynamicAdded.value) {
      addRoutesByRole(resolveRole())
      dynamicAdded.value = true
    }
  } catch (e) {
    // 预注册失败不应阻塞启动；守卫首跳会兜底
    console.warn('[router] syncInitialRoutes 失败，将由守卫兜底:', e)
  }
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
    // 必须用「原始 location」（仅 path/query/hash，不带 to 的 matched）重放，
    // 否则 Vue Router 会沿用旧的 not-found 匹配结果，无法重新解析已挂载的路由。
    return next({ path: to.path, query: to.query, hash: to.hash, replace: true })
  }

  // 3) 已登录但会话失效 → 清态跳登录
  if (!auth.isSessionValid()) {
    auth.clearSession()
    return next({ name: 'login', query: { redirect: to.fullPath } })
  }

  // 4) 已登录却落到 404：多为「路由尚未挂载」或手动输入了无效/越权路径。
  //    已登录态下绝不再跳登录页。分两种情况：
  //    (a) 命中名册中「当前角色有权访问」的已知路由，但路由因初始化竞态尚未挂载
  //        → 兜底补挂并重放当前目标，确保刷新后能停留在原页面（不再回仪表盘）。
  //    (b) 越权路径 / 完全无效路径 → 提示后回仪表盘。
  if (to.name === 'not-found') {
    const entry = matchRegistry(to.path)
    const role = resolveRole()
    if (entry && hasRole(role, entry.roles)) {
      // (a) 已知且有权访问，却因路由未挂载而落到 404（刷新竞态 / 初始化顺序等）
      //     → 兜底补挂并重放当前目标，确保刷新后停留在原页面。
      //     用 replayAttempted 按 path 去重，避免极端情况下无限重放。
      if (replayAttempted.value !== to.path) {
        replayAttempted.value = to.path
        addRoutesByRole(role)
        dynamicAdded.value = true
        auth.bumpRouteEpoch() // 通知菜单重算
        // 用原始 location 重放，强制重新匹配（见上方说明）
        return next({ path: to.path, query: to.query, hash: to.hash, replace: true })
      }
      // 已补挂重放一次仍 404（理论不可能），回仪表盘
      return next('/')
    }
    if (entry && !hasRole(role, entry.roles)) {
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
