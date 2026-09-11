// 全站签到记录领域状态（Pinia）：账号树 / 模糊搜索 / 选中账号 / 类型与状态筛选 /
// 服务端分页 / 任务列表 / 展开详情。数据与用户端「签到记录页」同源（B 平台历史任务
// 经后端代理读取，api/siteRecords.js），本 store 只做编排。
//
// [搜索口径] 树的模糊搜索在前端本地过滤（全量树一次拉取，两级数据量小）：
// 命中用户名 → 保留该用户全部账号；命中账号（登录标识或平台姓名）→ 仅保留命中账号。
// 有关键词时所有命中用户强制展开，由视图侧依据 keyword 判断。
//
// [竞态守卫] 列表请求带序号，仅采纳最新一次结果，杜绝快速切换账号/筛选时旧响应覆盖新数据。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchSiteTree, fetchAccountHistory, fetchAccountTaskDetail } from '@/api/siteRecords'

const EMPTY_OVERVIEW = { total: 0, finished: 0, unsigned: 0, needPhoto: 0, rate: 0 }

function toNum(v) {
  const n = Number(v)
  return Number.isNaN(n) ? v : n
}

export const useSiteRecordsStore = defineStore('siteRecords', () => {
  // ---- 账号树 ----
  const tree = ref([]) // [{ id, username, role, enabled, accounts: BAccount.to_dict[] }]
  const loadingTree = ref(false)
  const treeError = ref('')
  const treeLoaded = ref(false)
  // 树的模糊搜索关键词：本地过滤，命中用户名或账号（登录标识/平台姓名）
  const keyword = ref('')

  // ---- 选中账号与记录列表 ----
  const selectedAccountId = ref(null)
  const typeFilter = ref('all') // all | dorm | activity
  const statusFilter = ref('all') // all | signed | unsigned | needPhoto
  // 日期窗口（YYYY-MM-DD，可为 null）：任务区间与窗口重叠即入选，口径同后端
  const dateFrom = ref(null)
  const dateTo = ref(null)
  const page = ref(1)
  const pageSize = ref(10)
  const tasks = ref([])
  const total = ref(0)
  // 全历史口径统计（后端随列表响应返回；跟随类型+状态筛选，不受其他条件影响）
  const overview = ref({ ...EMPTY_OVERVIEW })
  const loadingRecords = ref(false)
  const refreshingRecords = ref(false)
  const listLoaded = ref(false)

  // 展开详情：taskId -> { loading, open, geoFence, logs, error }；成功结果缓存复用
  const details = ref({})
  const logsCache = ref({})

  // ---- 树的搜索过滤 ----
  // 账号可被「登录标识 / 平台姓名」命中；用户可被「用户名」命中（命中用户保留其全部账号）
  const filteredTree = computed(() => {
    const q = keyword.value.trim().toLowerCase()
    if (!q) return tree.value
    return tree.value
      .map((u) => {
        const userHit = u.username.toLowerCase().includes(q)
        const accounts = userHit
          ? u.accounts
          : u.accounts.filter((a) => {
              const name = (a.profile && a.profile.name) || ''
              return a.account.toLowerCase().includes(q) || name.toLowerCase().includes(q)
            })
        return { ...u, userHit, accounts }
      })
      .filter((u) => u.userHit || u.accounts.length > 0)
  })

  const treeCounts = computed(() => {
    const users = tree.value.length
    const accounts = tree.value.reduce((n, u) => n + u.accounts.length, 0)
    return { users, accounts }
  })

  const selectedAccount = computed(() => {
    for (const u of tree.value) {
      const hit = u.accounts.find((a) => toNum(a.id) === selectedAccountId.value)
      if (hit) return { ...hit, owner: u.username }
    }
    return null
  })

  // 账号状态点：凭证失效置灰；其余按最近一次本站调度结果（skip 视同已完成）
  function accDot(a) {
    if (a.verifyStatus !== 'ok') return 'off'
    const st = a.lastSignIn && a.lastSignIn.status
    return st === 'fail' ? 'err' : 'ok'
  }

  // ---- 账号树加载 ----
  async function loadTree() {
    loadingTree.value = true
    treeError.value = ''
    try {
      const res = await fetchSiteTree()
      tree.value = res.items
      treeLoaded.value = true
      // 默认选中首个账号（保持已有选中，跨刷新不丢）
      const flat = tree.value.flatMap((u) => u.accounts.map((a) => toNum(a.id)))
      if (flat.length && !flat.includes(selectedAccountId.value)) {
        selectedAccountId.value = flat[0]
      }
      if (!flat.length) selectedAccountId.value = null
    } catch (e) {
      treeError.value = e?.message || '加载账号树失败'
    } finally {
      loadingTree.value = false
    }
    await loadRecords()
  }

  // ---- 记录列表（服务端分页） ----
  let listSeq = 0
  async function loadList() {
    if (!selectedAccountId.value) {
      tasks.value = []
      total.value = 0
      overview.value = { ...EMPTY_OVERVIEW }
      return
    }
    const seq = ++listSeq
    const silent = listLoaded.value
    if (silent) {
      refreshingRecords.value = true
    } else {
      loadingRecords.value = true
    }
    try {
      const res = await fetchAccountHistory(selectedAccountId.value, {
        type: typeFilter.value,
        status: statusFilter.value,
        page: page.value,
        pageSize: pageSize.value,
        dateFrom: dateFrom.value || undefined,
        dateTo: dateTo.value || undefined,
      })
      if (seq !== listSeq) return // 竞态守卫：仅采纳最新请求
      tasks.value = res.items
      total.value = res.total
      if (res.overview) overview.value = res.overview
      listLoaded.value = true
    } finally {
      if (seq === listSeq) {
        loadingRecords.value = false
        refreshingRecords.value = false
      }
    }
  }

  // 账号/筛选切换的整备动作：重置分页、作废展开缓存
  async function loadRecords() {
    details.value = {}
    logsCache.value = {}
    page.value = 1
    await loadList()
  }

  function selectAccount(id) {
    const nid = toNum(id)
    if (selectedAccountId.value === nid) return
    selectedAccountId.value = nid
    // 切账号重置日期窗口（口径同用户端日历点选筛选：窗口不跨账号延续）
    dateFrom.value = null
    dateTo.value = null
    void loadRecords()
  }

  function setType(t) {
    if (typeFilter.value === t) return
    typeFilter.value = t
    void loadRecords()
  }

  function setStatus(s) {
    if (statusFilter.value === s) return
    statusFilter.value = s
    void loadRecords()
  }

  // 日期窗口：起止倒置时自动交换（避免后端筛出空集造成「看似无数据」的困惑）
  function setDateRange(from, to) {
    const f = from || null
    const t = to || null
    if (f && t && f > t) {
      dateFrom.value = t
      dateTo.value = f
    } else {
      dateFrom.value = f
      dateTo.value = t
    }
    page.value = 1
    void loadList()
  }

  function clearDateRange() {
    if (!dateFrom.value && !dateTo.value) return
    dateFrom.value = null
    dateTo.value = null
    page.value = 1
    void loadList()
  }

  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

  function setPage(p) {
    if (p >= 1 && p <= totalPages.value && p !== page.value) {
      page.value = p
      void loadList()
    }
  }

  function setPageSize(s) {
    const n = Number(s)
    if (n === pageSize.value) return
    pageSize.value = n
    page.value = 1
    void loadList()
  }

  function refresh() {
    void loadList()
  }

  // ---- 展开 / 收起：优先用缓存，否则懒加载围栏 + 签到凭证 ----
  async function toggleExpand(task) {
    const id = task.id
    const cur = details.value[id]
    if (cur && cur.open) {
      details.value = { ...details.value, [id]: { ...cur, open: false } }
      return
    }
    const cached = logsCache.value[id]
    if (cached) {
      details.value = {
        ...details.value,
        [id]: { loading: false, open: true, geoFence: cached.geoFence, logs: cached.logs, error: '' },
      }
      return
    }
    details.value = { ...details.value, [id]: { loading: true, open: true, geoFence: [], logs: [], error: '' } }
    try {
      const res = await fetchAccountTaskDetail(selectedAccountId.value, id, task.kind)
      logsCache.value = { ...logsCache.value, [id]: { logs: res.logs, geoFence: res.geoFence } }
      details.value = {
        ...details.value,
        [id]: { loading: false, open: true, geoFence: res.geoFence, logs: res.logs, error: '' },
      }
    } catch (e) {
      details.value = {
        ...details.value,
        [id]: { loading: false, open: true, geoFence: [], logs: [], error: e.message || '加载详情失败' },
      }
    }
  }

  function getDetail(id) {
    return details.value[id] || null
  }

  return {
    // 树
    tree,
    loadingTree,
    treeError,
    treeLoaded,
    keyword,
    filteredTree,
    treeCounts,
    accDot,
    // 选中与列表
    selectedAccountId,
    selectedAccount,
    typeFilter,
    statusFilter,
    dateFrom,
    dateTo,
    page,
    pageSize,
    totalPages,
    tasks,
    total,
    overview,
    loadingRecords,
    refreshingRecords,
    listLoaded,
    // 详情
    details,
    // 动作
    loadTree,
    loadRecords,
    selectAccount,
    setType,
    setStatus,
    setDateRange,
    clearDateRange,
    setPage,
    setPageSize,
    refresh,
    toggleExpand,
    getDetail,
  }
})
