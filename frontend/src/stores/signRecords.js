// 签到记录领域状态（Pinia）：收纳账号列表 / 选中账号 / 类型筛选 / 视图模式 /
// 日历月份 / 签到记录，把原本会散落在 SignRecordsView 里的数据编排逻辑下沉到 store，
// 视图只负责渲染与事件派发。后端接入时只需改 api/signRecords.js，本 store 与视图无需变动。
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { fetchAccounts, fetchSignRecords } from '@/api/signRecords'

const pad = (n) => String(n).padStart(2, '0')
function monthKeyOf(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`
}
function currentMonthKey() {
  return monthKeyOf(new Date())
}

export const useSignRecordsStore = defineStore('signRecords', () => {
  const accounts = ref([])
  const selectedAccountId = ref(null)
  const loadingAccounts = ref(false)
  const loadingRecords = ref(false)
  const records = ref([])

  // 类型筛选：all（全部）| dorm（寝室签到）| activity（活动签到）
  const typeFilter = ref('all')
  // 视图模式：list（列表）| calendar（日历）
  const viewMode = ref('list')
  // 当前日历展示年月（YYYY-MM）
  const calendarMonth = ref(currentMonthKey())
  // 列表分页：当前页 / 每页条数
  const page = ref(1)
  const pageSize = ref(10)

  // 已添加的平台账号：下拉选项（label 含账号与姓名，便于模糊搜索命中）
  const accountOptions = computed(() =>
    accounts.value.map((a) => ({
      value: a.id,
      label: a.profile && a.profile.name ? `${a.account} · ${a.profile.name}` : a.account
    }))
  )

  const selectedAccount = computed(
    () => accounts.value.find((a) => a.id === selectedAccountId.value) || null
  )

  // 按类型过滤后的记录（类型切换为纯前端筛选，无需重新请求）
  const typedRecords = computed(() =>
    typeFilter.value === 'all'
      ? records.value
      : records.value.filter((r) => r.type === typeFilter.value)
  )

  // 统计卡片：仅当前所选账号 + 当前类型下的数据
  const stats = computed(() => {
    const list = typedRecords.value
    const signed = list.filter((r) => r.status === 'signed').length
    const unsigned = list.filter((r) => r.status === 'unsigned').length
    return { signed, unsigned, total: list.length }
  })

  // 列表视图：按日期+时间倒序（全量，用于统计与空态判断）
  const listRows = computed(() =>
    [...typedRecords.value].sort((a, b) => `${b.date}${b.time}`.localeCompare(`${a.date}${a.time}`))
  )

  // 分页派生
  const total = computed(() => listRows.value.length)
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
  const pagedRows = computed(() => {
    const start = (page.value - 1) * pageSize.value
    return listRows.value.slice(start, start + pageSize.value)
  })

  // 按日期聚合，供日历视图着色（漏签优先标红）
  const byDate = computed(() => {
    const map = {}
    for (const r of typedRecords.value) {
      const bucket = (map[r.date] = map[r.date] || { signed: 0, unsigned: 0 })
      if (r.status === 'signed') bucket.signed += 1
      else if (r.status === 'unsigned') bucket.unsigned += 1
    }
    return map
  })

  const isCurrentMonth = computed(() => calendarMonth.value === currentMonthKey())

  async function loadAccounts() {
    loadingAccounts.value = true
    try {
      accounts.value = await fetchAccounts()
      // 默认展示第一个账号的签到记录
      if (!selectedAccountId.value && accounts.value.length) {
        selectedAccountId.value = accounts.value[0].id
      }
    } finally {
      loadingAccounts.value = false
    }
  }

  async function loadRecords() {
    if (!selectedAccountId.value) {
      records.value = []
      return
    }
    loadingRecords.value = true
    try {
      records.value = await fetchSignRecords(selectedAccountId.value, {
        accountName: selectedAccount.value && selectedAccount.value.profile
          ? selectedAccount.value.profile.name
          : ''
      })
    } finally {
      loadingRecords.value = false
      page.value = 1
    }
  }

  function selectAccount(id) {
    selectedAccountId.value = id
  }

  function setType(t) {
    typeFilter.value = t
    page.value = 1
  }

  function setView(v) {
    viewMode.value = v
  }

  function prevMonth() {
    const [y, m] = calendarMonth.value.split('-').map(Number)
    const d = new Date(y, m - 2, 1)
    calendarMonth.value = monthKeyOf(d)
  }
  function nextMonth() {
    const [y, m] = calendarMonth.value.split('-').map(Number)
    const d = new Date(y, m, 1)
    calendarMonth.value = monthKeyOf(d)
  }
  function backToCurrentMonth() {
    calendarMonth.value = currentMonthKey()
  }

  // 分页控制：跳页（边界保护）/ 改每页条数（回到第 1 页）
  function onPageChange(p) {
    if (p >= 1 && p <= totalPages.value) page.value = p
  }
  function onPageSizeChange(s) {
    pageSize.value = Number(s)
    page.value = 1
  }

  // 选中账号变化即重新拉取第三方数据（仅单个账号）
  watch(selectedAccountId, () => {
    loadRecords()
  })

  return {
    accounts,
    selectedAccountId,
    loadingAccounts,
    loadingRecords,
    records,
    typeFilter,
    viewMode,
    calendarMonth,
    accountOptions,
    selectedAccount,
    typedRecords,
    stats,
    listRows,
    total,
    totalPages,
    pagedRows,
    page,
    pageSize,
    byDate,
    isCurrentMonth,
    loadAccounts,
    loadRecords,
    selectAccount,
    setType,
    setView,
    prevMonth,
    nextMonth,
    backToCurrentMonth,
    onPageChange,
    onPageSizeChange
  }
})
