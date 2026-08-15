// 用户管理领域状态（Pinia）：收纳列表 / 筛选 / 分页 / 增删改与汇总，
// 把原本散落在 UserManagementView 里的数据编排逻辑下沉到 store，
// 视图只负责渲染、展示辅助与 toast 提示。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getUsers, createUser, updateUser, setUserStatus, deleteUser } from '@/api/users'

export const useUsersStore = defineStore('users', () => {
  const list = ref([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(10)
  const keyword = ref('')
  const roleFilter = ref('')
  const loading = ref(false)
  const summary = ref({ total_users: 0, enabled: 0, disabled: 0, total_quota: 0, used_quota: 0 })

  // 乐观删除：后端删除为桩，标记隐藏的 id 并在拉取后过滤，刷新页面前保持不可见
  const hiddenIds = ref(new Set())

  // 弹窗状态
  const showForm = ref(false)
  const formMode = ref('add')
  const editingUser = ref(null)
  const formSubmitting = ref(false)
  const showDelete = ref(false)
  const deletingUser = ref(null)
  const deleting = ref(false)

  const rows = computed(() => list.value.filter((i) => !hiddenIds.value.has(i.user_id)))
  const displayTotal = computed(() => Math.max(0, total.value - hiddenIds.value.size))
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
    loading.value = true
    try {
      const res = await getUsers(buildParams())
      list.value = res.items || []
      total.value = res.total || 0
      if (res.summary) summary.value = res.summary
      // 删除后可能使当前页越界，做收敛
      const tp = Math.max(1, Math.ceil(displayTotal.value / pageSize.value))
      if (page.value > tp) page.value = tp
    } finally {
      loading.value = false
    }
  }

  // 关键词搜索防抖
  let kwTimer = null
  function onKeywordInput() {
    if (kwTimer) clearTimeout(kwTimer)
    kwTimer = setTimeout(() => {
      page.value = 1
      fetchUsers()
    }, 300)
  }
  function onFilterChange() {
    page.value = 1
    fetchUsers()
  }
  function onPageChange(p) {
    page.value = p
    fetchUsers()
  }
  function onPageSizeChange(size) {
    pageSize.value = size
    page.value = 1
    fetchUsers()
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

  // 删除（后端为桩，前端乐观移除并标记隐藏；同步汇总计数，由调用方负责 toast）
  async function confirmDelete() {
    if (!deletingUser.value) return
    deleting.value = true
    const user = deletingUser.value
    try {
      await deleteUser(user.user_id)
      hiddenIds.value = new Set(hiddenIds.value).add(user.user_id)
      total.value = Math.max(0, total.value - 1)
      summary.value.total_users = Math.max(0, summary.value.total_users - 1)
      summary.value.used_quota = Math.max(0, summary.value.used_quota - (user.used_quota || 0))
      summary.value.total_quota = Math.max(0, summary.value.total_quota - (user.quota || 0))
      if (user.enabled) summary.value.enabled = Math.max(0, summary.value.enabled - 1)
      else summary.value.disabled = Math.max(0, summary.value.disabled - 1)
      showDelete.value = false
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
    summary,
    hiddenIds,
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
