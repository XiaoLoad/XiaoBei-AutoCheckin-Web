// 账号管理领域状态（Pinia）：收纳列表 / 筛选 / 分页 / 增删改，
// 把原本散落在 AccountManagementView 里的数据编排逻辑下沉到 store，
// 视图只负责渲染与事件派发。后端接入时只需改 api/accounts.js，本 store 与视图无需变动。
import { defineStore } from 'pinia'
import { useRefreshBusStore } from '@/stores/refreshBus'
import { ref, computed, watch } from 'vue'
import { fetchAccounts, createAccount, updateAccount, deleteAccount } from '@/api/accounts'
import { fetchDormMembers } from '@/api/groupPush'
import { accountTypeCode } from '@/utils/accountType'

// 成员地图归一化：[{accountId, groupId, groupName}] → { [accountId]: {id, name, count} }。
// 后端按分组 id 倒序返回，同一账号多次出现时保留首个（最新的组）并累计个数。
export function toDormGroupMap(rows) {
  const map = {}
  for (const r of rows) {
    const k = String(r.accountId)
    if (map[k]) map[k].count += 1
    else map[k] = { id: r.groupId, name: r.groupName, count: 1 }
  }
  return map
}

export const useAccountsStore = defineStore('accounts', () => {
  const refreshBus = useRefreshBusStore()
  const loading = ref(false)
  // 无感刷新：已有数据时后台静默换新（视图仅降透明），loading 只用于真正的首次加载
  const refreshing = ref(false)
  const loaded = ref(false)
  let loadSeq = 0
  const accounts = ref([])

  // 账号 → 所属寝室分组（卡片要标注）。分组归属存在 push_group_members，账号列表接口
  // 不带这层，故随列表一起取回；多个分组时取最新的那个（后端按分组 id 倒序），并记个数。
  const dormGroups = ref({})
  // 归属是否已取到：没取到就不能显示「未分组」——那是在替服务端下结论，宁可留空
  const dormLoaded = ref(false)

  // 筛选状态（前端演示；后端接入时作为查询参数传递，见 api/accounts.js）
  const keyword = ref('')
  const typeFilter = ref('')
  const signFilter = ref('')
  const enabledFilter = ref('')

  // 分页状态（复用用户管理页 Pagination 组件）
  const page = ref(1)
  const pageSize = ref(10)

  // 弹窗状态
  const showForm = ref(false)
  const formMode = ref('add')
  const editing = ref(null)
  const submitting = ref(false)
  const showDelete = ref(false)
  const deleting = ref(false)
  const deletingItem = ref(null)

  // 任意筛选 / 搜索命中时显示「重置」
  const hasFilter = computed(
    () => !!keyword.value.trim() || !!typeFilter.value || !!signFilter.value || !!enabledFilter.value
  )

  // 模糊搜索 + 三项筛选（前端演示）
  // 类型筛选与类型徽标同口径：四分类严格匹配（general/dorm/activity/none 选一），
  // 判定唯一出处 utils/accountType.js。不读账号自身的 type 字段（该字段已废弃展示用途）。
  const filtered = computed(() => {
    const kw = keyword.value.trim().toLowerCase()
    return accounts.value.filter((a) => {
      if (typeFilter.value && accountTypeCode(a.signTasks) !== typeFilter.value) return false
      if (enabledFilter.value !== '' && String(a.enabled) !== enabledFilter.value) return false
      if (signFilter.value) {
        const st = (a.lastSignIn && a.lastSignIn.status) || 'never'
        if (st !== signFilter.value) return false
      }
      if (kw) {
        const p = a.profile || {}
        const hit =
          (a.account || '').toLowerCase().includes(kw) ||
          (p.name || '').toLowerCase().includes(kw) ||
          (p.studentNo || '').toLowerCase().includes(kw)
        if (!hit) return false
      }
      return true
    })
  })

  // 当前页切片（分页逻辑核心）
  const pagedRows = computed(() => {
    const start = (page.value - 1) * pageSize.value
    return filtered.value.slice(start, start + pageSize.value)
  })

  // 筛选或关键词变化时回到第一页
  watch([keyword, typeFilter, signFilter, enabledFilter], () => {
    page.value = 1
  })

  // 数据量变化（筛选/删除）导致当前页越界时收敛
  watch(filtered, (list) => {
    const tp = Math.max(1, Math.ceil(list.length / pageSize.value))
    if (page.value > tp) page.value = tp
  })

  // 清空筛选：关键词也算筛选（hasFilter 把 keyword 计在内），漏掉它会出现
  // 「重置可用但点了没反应」——只有搜索词时按钮亮着、点下去列表纹丝不动
  function resetFilters() {
    keyword.value = ''
    typeFilter.value = ''
    signFilter.value = ''
    enabledFilter.value = ''
  }

  async function load() {
    const first = !loaded.value
    if (first) loading.value = true
    else {
      refreshing.value = true
      refreshBus.begin()
    }
    const seq = ++loadSeq
    try {
      // 后端接入时此处可传 { keyword, type, signStatus, enabled } 由服务端过滤与分页
      // 归属拉取失败只降级自己（卡片留空），不能连带把账号列表也拖挂
      const [list, membership] = await Promise.all([
        fetchAccounts(),
        fetchDormMembers().catch(() => null)
      ])
      if (seq !== loadSeq) return // 竞态守卫：仅采纳最新请求
      accounts.value = list
      if (membership) {
        dormGroups.value = toDormGroupMap(membership)
        dormLoaded.value = true
      }
      loaded.value = true
    } finally {
      if (!first) refreshBus.end()
      if (seq === loadSeq) {
        loading.value = false
        refreshing.value = false
      }
    }
  }

  function onPageChange(p) {
    page.value = p
  }
  function onPageSizeChange(size) {
    pageSize.value = size
    page.value = 1
  }

  function openAdd() {
    formMode.value = 'add'
    editing.value = null
    showForm.value = true
  }
  function openEdit(item) {
    formMode.value = 'edit'
    editing.value = item
    showForm.value = true
  }
  function closeForm() {
    showForm.value = false
  }

  async function onSubmitForm(payload) {
    submitting.value = true
    try {
      if (formMode.value === 'add') {
        const created = await createAccount(payload)
        accounts.value.unshift(created)
      } else if (editing.value) {
        const updated = await updateAccount(editing.value.id, payload)
        const i = accounts.value.findIndex((a) => a.id === updated.id)
        if (i !== -1) accounts.value[i] = updated
      }
      showForm.value = false
    } finally {
      submitting.value = false
    }
  }

  // 启用 / 禁用切换（乐观更新，由调用方负责 toast 提示）
  async function onToggle(item) {
    const updated = await updateAccount(item.id, { enabled: !item.enabled })
    const i = accounts.value.findIndex((a) => a.id === item.id)
    if (i !== -1) accounts.value[i] = updated
  }

  function askDelete(item) {
    deletingItem.value = item
    showDelete.value = true
  }
  function closeDelete() {
    showDelete.value = false
  }

  async function confirmDelete() {
    const target = deletingItem.value
    if (!target) return
    deleting.value = true
    try {
      await deleteAccount(target.id)
      accounts.value = accounts.value.filter((a) => a.id !== target.id)
      // 仅成功才关弹窗并清目标：失败时保留 deletingItem，弹窗保持可重试
      // （此前 finally 无条件清空，失败后弹窗仍开着但再点确认静默无效）
      showDelete.value = false
      deletingItem.value = null
    } finally {
      deleting.value = false
    }
  }

  return {
    loading,
    refreshing,
    accounts,
    dormGroups,
    dormLoaded,
    keyword,
    typeFilter,
    signFilter,
    enabledFilter,
    page,
    pageSize,
    showForm,
    formMode,
    editing,
    submitting,
    showDelete,
    deleting,
    deletingItem,
    hasFilter,
    filtered,
    pagedRows,
    resetFilters,
    load,
    onPageChange,
    onPageSizeChange,
    openAdd,
    openEdit,
    closeForm,
    onSubmitForm,
    onToggle,
    askDelete,
    closeDelete,
    confirmDelete
  }
})
