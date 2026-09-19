// 用户管理领域状态（Pinia）：收纳列表 / 筛选 / 分页 / 增删改与汇总，
// 把原本散落在 UserManagementView 里的数据编排逻辑下沉到 store，
// 视图只负责渲染、展示辅助与 toast 提示。
import { defineStore } from 'pinia'
import { useRefreshBusStore } from '@/stores/refreshBus'
import { ref, computed } from 'vue'
import { getUsers, createUser, updateUser, setUserStatus, deleteUser } from '@/api/users'

export const useUsersStore = defineStore('users', () => {
  const refreshBus = useRefreshBusStore()
  const list = ref([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(10)
  const keyword = ref('')
  const roleFilter = ref('')
  const loading = ref(false)
  // 无感刷新：已有数据时后台静默换新（视图仅降透明），loading 只用于真正的首次加载；
  // loaded 标记"是否完成过一次成功拉取"，区分首载与刷新（列表为空也可能是合法空结果）
  const refreshing = ref(false)
  const loaded = ref(false)
  let fetchSeq = 0

  const summary = ref({ total_users: 0, enabled: 0, disabled: 0, total_quota: 0, used_quota: 0 })

  // 弹窗状态
  const showForm = ref(false)
  const formMode = ref('add')
  const editingUser = ref(null)
  const formSubmitting = ref(false)
  const showDelete = ref(false)
  const deletingUser = ref(null)
  const deleting = ref(false)

  // 列表与总数直接来自服务端：删除是真的删，删完重新取，不再本地假装隐藏
  const rows = computed(() => list.value)
  const displayTotal = computed(() => total.value)
  const quotaRate = computed(() =>
    summary.value.total_quota > 0
      ? Math.min(100, Math.round((summary.value.used_quota / summary.value.total_quota) * 100))
      : 0
  )

  function buildParams() {
    const params = { page: page.value, page_size: pageSize.value }
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    if (roleFilter.value) params.role = roleFilter.value
    return params
  }

  async function fetchUsers() {
    const first = !loaded.value
    if (first) loading.value = true
    else {
      refreshing.value = true
      refreshBus.begin()
    }
    const seq = ++fetchSeq
    try {
      const res = await getUsers(buildParams())
      if (seq !== fetchSeq) return // 竞态守卫：仅采纳最新请求
      list.value = res.items || []
      total.value = res.total || 0
      if (res.summary) summary.value = res.summary
      // 删除后可能使当前页越界，做收敛
      const tp = Math.max(1, Math.ceil(displayTotal.value / pageSize.value))
      if (page.value > tp) page.value = tp
      loaded.value = true
    } finally {
      if (!first) refreshBus.end()
      if (seq === fetchSeq) {
        loading.value = false
        refreshing.value = false
      }
    }
  }

  // 关键词搜索防抖
  let kwTimer = null
  function onKeywordInput() {
    if (kwTimer) clearTimeout(kwTimer)
    kwTimer = setTimeout(() => {
      page.value = 1
      fetchUsers().catch(() => {}) // 失败已由 request.js 全局 toast，这里只吞 rejection
    }, 300)
  }
  function onFilterChange() {
    page.value = 1
    fetchUsers().catch(() => {})
  }
  function onPageChange(p) {
    page.value = p
    fetchUsers().catch(() => {})
  }
  function onPageSizeChange(size) {
    pageSize.value = size
    page.value = 1
    fetchUsers().catch(() => {})
  }

  function openAdd() {
    formMode.value = 'add'
    editingUser.value = null
    showForm.value = true
  }
  function openEdit(item) {
    formMode.value = 'edit'
    editingUser.value = item
    showForm.value = true
  }
  function closeForm() {
    showForm.value = false
  }

  async function handleFormSubmit(payload) {
    formSubmitting.value = true
    try {
      if (formMode.value === 'add') {
        await createUser(payload)
      } else {
        await updateUser(editingUser.value.user_id, payload)
      }
      showForm.value = false
      page.value = 1
      await fetchUsers()
    } finally {
      formSubmitting.value = false
    }
  }

  // 禁用 / 启用（可逆；乐观更新并同步汇总计数，由调用方负责 toast）
  async function toggleStatus(item) {
    const next = !item.enabled
    await setUserStatus(item.user_id, next)
    item.enabled = next
    if (next) {
      summary.value.enabled += 1
      summary.value.disabled = Math.max(0, summary.value.disabled - 1)
    } else {
      summary.value.disabled += 1
      summary.value.enabled = Math.max(0, summary.value.enabled - 1)
    }
  }

  function openDelete(item) {
    deletingUser.value = item
    showDelete.value = true
  }
  function closeDelete() {
    showDelete.value = false
  }

  // 删除：后端物理删除并级联清理名下账号/任务/记录，成功后重新取列表与汇总
  // （曾经是桩接口，前端靠本地隐藏 id 装作删掉了，刷新就穿帮；接口转真后一并去掉）
  // 失败（如共享资源仍被他人引用 → 409）由 request.js 全局 toast，这里不吞错、只向上抛
  async function confirmDelete() {
    if (!deletingUser.value) return
    deleting.value = true
    const user = deletingUser.value
    try {
      await deleteUser(user.user_id)
      showDelete.value = false
      // 删除可能使当前页越界，fetchUsers 内部会收敛页码
      await fetchUsers()
    } finally {
      deleting.value = false
    }
  }

  return {
    list,
    total,
    page,
    pageSize,
    keyword,
    roleFilter,
    loading,
    refreshing,
    summary,
    showForm,
    formMode,
    editingUser,
    formSubmitting,
    showDelete,
    deletingUser,
    deleting,
    rows,
    displayTotal,
    quotaRate,
    fetchUsers,
    onKeywordInput,
    onFilterChange,
    onPageChange,
    onPageSizeChange,
    openAdd,
    openEdit,
    closeForm,
    handleFormSubmit,
    toggleStatus,
    openDelete,
    closeDelete,
    confirmDelete
  }
})
