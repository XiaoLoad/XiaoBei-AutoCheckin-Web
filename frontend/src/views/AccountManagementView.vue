<template>
  <!-- 根容器：占满父级高度，列表卡片 flex-1 内部滚动，解决高度过低问题 -->
  <div class="flex flex-1 min-h-0 flex-col gap-6">
    <!-- 统一操作栏：搜索 + 筛选 + 刷新 + 重置 + 新增，合并为一卡，简约单行布局。
         relative z-30 提升堆叠层级，确保内部下拉面板不被下方列表卡片遮挡。 -->
    <div class="dash-card fade-up relative z-30 shrink-0 p-3 sm:p-4">
      <div class="flex flex-wrap items-center gap-2 sm:gap-3">
        <!-- 搜索框：缩小占比，不再占满整行 -->
        <div class="relative w-full sm:w-52">
          <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input
            v-model="keyword"
            type="text"
            placeholder="搜索账号 / 姓名 / 学号"
            class="login-input py-2 pl-9 text-sm"
          />
        </div>

        <!-- 筛选：以占位符代替列标签，视觉更轻量 -->
        <div class="w-full sm:w-36">
          <BaseSelect v-model="typeFilter" :options="typeOptions" placeholder="签到类型" />
        </div>
        <div class="w-full sm:w-36">
          <BaseSelect v-model="signFilter" :options="signOptions" placeholder="签到状态" />
        </div>
        <div class="w-full sm:w-32">
          <BaseSelect v-model="enabledFilter" :options="enabledOptions" placeholder="启用状态" />
        </div>

        <!-- 右侧操作：刷新 / 重置（有筛选时显示）/ 新增 -->
        <div class="ml-auto flex items-center gap-2">
          <button
            type="button"
            class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-ink/10 text-ink-muted transition hover:bg-cloud hover:text-ink"
            aria-label="刷新"
            :disabled="loading"
            @click="load"
          >
            <Icon name="refresh" :size="17" :class="loading && 'spin-refresh'" />
          </button>
          <button
            v-if="hasFilter"
            type="button"
            class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-ink/10 px-3 text-sm font-medium text-ink-soft transition hover:bg-cloud"
            @click="resetFilters"
          >
            <Icon name="close" :size="14" />重置
          </button>
          <button
            type="button"
            class="inline-flex items-center justify-center gap-1.5 rounded-xl bg-brand px-3.5 py-2 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark focus:outline-none focus:ring-4 focus:ring-brand/30 sm:px-4"
            @click="openAdd"
          >
            <Icon name="plus" :size="17" />
            <span class="hidden sm:inline">新增账号</span>
            <span class="sm:hidden">新增</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 列表卡片：桌面表格 + 移动卡片，卡片 flex-1 内部滚动，底部固定分页 -->
    <div class="dash-card fade-up flex flex-1 min-h-0 flex-col overflow-hidden rounded-2xl">
      <!-- 桌面表格（≥1024） -->
      <div class="xb-scroll hidden min-h-0 flex-1 overflow-auto lg:block">
        <table class="w-full table-fixed text-left text-sm">
          <colgroup>
            <col class="w-[14%]" />
            <col class="w-[30%]" />
            <col class="w-[10%]" />
            <col class="w-[15%]" />
            <col class="w-[12%]" />
            <col class="w-[19%]" />
          </colgroup>
          <thead>
            <tr class="border-b border-ink/10 text-ink-muted">
              <th class="sticky top-0 z-10 bg-white px-3 py-2.5 font-medium align-middle whitespace-nowrap">账号</th>
              <th class="sticky top-0 z-10 bg-white px-3 py-2.5 font-medium align-middle whitespace-nowrap">个人信息</th>
              <th class="sticky top-0 z-10 bg-white px-3 py-2.5 font-medium align-middle whitespace-nowrap">签到类型</th>
              <th class="sticky top-0 z-10 bg-white px-3 py-2.5 font-medium align-middle whitespace-nowrap">上一次签到</th>
              <th class="sticky top-0 z-10 bg-white px-3 py-2.5 font-medium align-middle whitespace-nowrap">启用状态</th>
              <th class="sticky top-0 z-10 bg-white px-3 py-2.5 text-left font-medium align-middle whitespace-nowrap">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" class="border-b border-ink/5">
              <td colspan="6" class="px-3 py-12 text-center text-ink-muted">加载中…</td>
            </tr>
            <tr v-else-if="pagedRows.length === 0" class="border-b border-ink/5">
              <td colspan="6" class="px-3 py-16 text-center">
                <div class="flex flex-col items-center gap-2 text-ink-muted">
                  <Icon name="user" :size="28" class="opacity-50" />
                  <span>暂无账号，点击「新增账号」添加你的第一个 B 平台账号。</span>
                </div>
              </td>
            </tr>
            <tr
              v-for="item in pagedRows"
              v-else
              :key="item.id"
              class="border-b border-ink/5 transition last:border-0 hover:bg-cloud/40"
            >
              <!-- 账号 -->
              <td class="px-3 py-3 align-top">
                <p class="truncate font-medium text-ink">{{ item.account }}</p>
              </td>
              <!-- 个人信息：完整展示，允许换行，增大行高 -->
              <td class="px-3 py-3 align-top">
                <template v-if="item.profile && item.profile.name">
                  <p class="font-medium text-ink break-words">{{ item.profile.name }}</p>
                  <p class="mt-0.5 text-xs tabular-nums text-ink-muted">{{ item.profile.studentNo || '—' }}</p>
                  <p class="mt-0.5 text-xs leading-relaxed text-ink-muted break-words">
                    {{ [item.profile.college, item.profile.major, item.profile.className].filter(Boolean).join(' · ') || '—' }}
                  </p>
                </template>
                <span v-else class="text-xs text-ink-muted">未获取</span>
              </td>
              <!-- 签到类型 -->
              <td class="px-3 py-3 align-top">
                <span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap" :class="typeMeta(item.type).cls">
                  {{ typeMeta(item.type).label }}
                </span>
              </td>
              <!-- 上一次签到（时间 / 状态） -->
              <td class="px-3 py-3 align-top">
                <p class="tabular-nums text-ink-soft">{{ item.lastSignIn && item.lastSignIn.time ? item.lastSignIn.time : '—' }}</p>
                <div class="mt-1 flex items-center gap-1.5 whitespace-nowrap text-xs font-medium" :class="signMeta(item).cls">
                  <span class="h-1.5 w-1.5 rounded-full" :class="signMeta(item).dot" />
                  {{ signMeta(item).label }}
                </div>
              </td>
              <!-- 启用状态 -->
              <td class="px-3 py-3 align-top">
                <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap" :class="item.enabled ? 'bg-success/10 text-success' : 'bg-ink/5 text-ink-muted'">
                  <span class="h-1.5 w-1.5 rounded-full" :class="item.enabled ? 'bg-success' : 'bg-ink/30'" />
                  {{ item.enabled ? '启用' : '禁用' }}
                </span>
              </td>
              <!-- 操作 -->
              <td class="px-3 py-3 align-top">
                <div class="flex flex-nowrap items-center justify-start gap-1">
                  <button class="inline-flex items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1.5 text-[13px] font-medium text-brand transition hover:bg-brand/10" @click="openEdit(item)">
                    <Icon name="edit" :size="14" />编辑
                  </button>
                  <button class="inline-flex items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1.5 text-[13px] font-medium text-ink-muted transition hover:bg-cloud" @click="onToggle(item)">
                    <Icon :name="item.enabled ? 'x-circle' : 'check-circle'" :size="14" />{{ item.enabled ? '禁用' : '启用' }}
                  </button>
                  <button class="inline-flex items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1.5 text-[13px] font-medium text-danger transition hover:bg-danger/10" @click="askDelete(item)">
                    <Icon name="trash" :size="14" />删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 移动端卡片列表（<1024） -->
      <div v-if="loading" class="flex flex-1 items-center justify-center text-sm text-ink-muted lg:hidden">加载中…</div>
      <div v-else-if="filtered.length === 0" class="flex flex-1 flex-col items-center justify-center gap-2 px-4 text-center text-ink-muted lg:hidden">
        <Icon name="user" :size="28" class="opacity-50" />
        <span>暂无账号，点击「新增账号」添加。</span>
      </div>
      <div
        v-else
        class="xb-scroll min-h-0 flex-1 space-y-3 overflow-auto p-3 lg:hidden"
      >
        <div
          v-for="item in pagedRows"
          :key="item.id"
          class="rounded-xl border border-ink/10 bg-white p-4"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="truncate font-semibold text-ink">{{ item.account }}</p>
              <div class="mt-1.5 flex flex-wrap items-center gap-1.5 whitespace-nowrap">
                <span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium" :class="typeMeta(item.type).cls">
                  {{ typeMeta(item.type).label }}
                </span>
                <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium" :class="item.enabled ? 'bg-success/10 text-success' : 'bg-ink/5 text-ink-muted'">
                  <span class="h-1.5 w-1.5 rounded-full" :class="item.enabled ? 'bg-success' : 'bg-ink/30'" />
                  {{ item.enabled ? '启用' : '禁用' }}
                </span>
              </div>
            </div>
          </div>

          <!-- 个人信息预留区（完整展示，允许换行） -->
          <div class="mt-3 rounded-xl bg-cloud/50 px-3 py-2.5 text-sm">
            <template v-if="item.profile && item.profile.name">
              <div class="flex items-center justify-between gap-2">
                <span class="font-medium text-ink-soft break-words">{{ item.profile.name }}</span>
                <span class="shrink-0 text-xs text-ink-muted tabular-nums">{{ item.profile.studentNo || '—' }}</span>
              </div>
              <p class="mt-0.5 text-xs leading-relaxed text-ink-muted break-words">
                {{ [item.profile.college, item.profile.major, item.profile.className].filter(Boolean).join(' · ') || '—' }}
              </p>
            </template>
            <span v-else class="text-xs text-ink-muted">个人信息：登录后自动获取</span>
          </div>

          <!-- 上一次签到 -->
          <div class="mt-3 flex items-center justify-between">
            <span class="text-xs text-ink-muted">上一次签到</span>
            <div class="flex items-center gap-2">
              <span class="tabular-nums text-sm text-ink-soft">{{ item.lastSignIn && item.lastSignIn.time ? item.lastSignIn.time : '—' }}</span>
              <span class="inline-flex items-center gap-1 text-xs font-medium" :class="signMeta(item).cls">
                <span class="h-1.5 w-1.5 rounded-full" :class="signMeta(item).dot" />
                {{ signMeta(item).label }}
              </span>
            </div>
          </div>

          <div class="mt-3 flex items-center gap-2">
            <button class="flex-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-brand transition hover:bg-brand/10" @click="openEdit(item)">编辑</button>
            <button class="flex-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-ink-muted transition hover:bg-cloud" @click="onToggle(item)">{{ item.enabled ? '禁用' : '启用' }}</button>
            <button class="flex-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-danger transition hover:bg-danger/10" @click="askDelete(item)">删除</button>
          </div>
        </div>
      </div>

      <!-- 分页（复用用户管理页 Pagination 组件） -->
      <div v-if="!loading && filtered.length > 0" class="shrink-0 border-t border-ink/5 px-3 py-2">
        <Pagination
          :page="page"
          :page-size="pageSize"
          :total="filtered.length"
          :page-size-options="[10, 20, 50]"
          :disabled="loading"
          @update:page="onPageChange"
          @update:page-size="onPageSizeChange"
        />
      </div>
    </div>

    <!-- 新增 / 编辑弹窗 -->
    <AccountFormModal
      v-model="showForm"
      :mode="formMode"
      :account="editing"
      :submitting="submitting"
      @submit="onSubmitForm"
      @cancel="showForm = false"
    />

    <!-- 删除二次确认 -->
    <ConfirmModal
      v-model="showDelete"
      title="删除账号"
      :message="deletingItem ? `确定要删除账号「${deletingItem.account}」吗？删除后其打卡配置与日志将一并移除，且不可恢复。` : ''"
      icon="trash"
      confirm-text="删除"
      cancel-text="取消"
      danger
      :confirming="deleting"
      @confirm="confirmDelete"
      @cancel="showDelete = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import Pagination from '@/components/Pagination.vue'
import AccountFormModal from '@/components/AccountFormModal.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import {
  fetchAccounts,
  createAccount,
  updateAccount,
  deleteAccount
} from '@/api/accounts'

const loading = ref(false)
const accounts = ref([])
const keyword = ref('')

// 筛选状态（前端演示；后端接入时将作为查询参数传递，见 api/accounts.js）
const typeFilter = ref('')
const signFilter = ref('')
const enabledFilter = ref('')

// 分页状态（复用用户管理页 Pagination 组件）
const page = ref(1)
const pageSize = ref(10)

// 自定义下拉选项（通用数据：{ label, value }）
const typeOptions = [
  { label: '全部类型', value: '' },
  { label: '寝室', value: 'dorm' },
  { label: '活动', value: 'activity' },
  { label: '通用', value: 'general' }
]
const signOptions = [
  { label: '全部状态', value: '' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'fail' },
  { label: '跳过', value: 'skip' },
  { label: '从未签到', value: 'never' }
]
const enabledOptions = [
  { label: '全部状态', value: '' },
  { label: '启用', value: 'true' },
  { label: '禁用', value: 'false' }
]

// 任意筛选 / 搜索命中时显示「重置」
const hasFilter = computed(
  () => !!keyword.value.trim() || !!typeFilter.value || !!signFilter.value || !!enabledFilter.value
)

const showForm = ref(false)
const formMode = ref('add')
const editing = ref(null)
const submitting = ref(false)

const showDelete = ref(false)
const deleting = ref(false)
const deletingItem = ref(null)

// 签到类型映射
function typeMeta(type) {
  if (type === 'activity') return { label: '活动', cls: 'bg-info/10 text-info' }
  if (type === 'general') return { label: '通用', cls: 'bg-ink/10 text-ink-soft' }
  return { label: '寝室', cls: 'bg-brand/10 text-brand' }
}

// 上一次签到状态映射
function signMeta(item) {
  const s = item.lastSignIn
  const status = (s && s.status) || 'never'
  if (status === 'success') return { label: '成功', cls: 'text-success', dot: 'bg-success' }
  if (status === 'fail') return { label: '失败', cls: 'text-danger', dot: 'bg-danger' }
  if (status === 'skip') return { label: '跳过', cls: 'text-warning', dot: 'bg-warning' }
  return { label: '从未签到', cls: 'text-ink-muted', dot: 'bg-ink/30' }
}

// 模糊搜索 + 三项筛选（前端演示）
const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return accounts.value.filter((a) => {
    if (typeFilter.value && a.type !== typeFilter.value) return false
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

function resetFilters() {
  typeFilter.value = ''
  signFilter.value = ''
  enabledFilter.value = ''
}

async function load() {
  loading.value = true
  try {
    // 后端接入时此处可传 { keyword, type, signStatus, enabled } 由服务端过滤与分页
    accounts.value = await fetchAccounts()
  } finally {
    loading.value = false
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

// 启用 / 禁用切换
async function onToggle(item) {
  const updated = await updateAccount(item.id, { enabled: !item.enabled })
  const i = accounts.value.findIndex((a) => a.id === item.id)
  if (i !== -1) accounts.value[i] = updated
}

function askDelete(item) {
  deletingItem.value = item
  showDelete.value = true
}

async function confirmDelete() {
  if (!deletingItem.value) return
  deleting.value = true
  try {
    await deleteAccount(deletingItem.value.id)
    accounts.value = accounts.value.filter((a) => a.id !== deletingItem.value.id)
    showDelete.value = false
  } finally {
    deleting.value = false
    deletingItem.value = null
  }
}

load()
</script>

<style scoped>
/* 仅刷新图标旋转，按钮容器与其它元素保持静止 */
.spin-refresh {
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .spin-refresh {
    animation: none;
  }
}
/* 预留滚动条宽度，防止纵向滚动时表头与内容列错位 */
.xb-scroll {
  scrollbar-gutter: stable;
}
</style>
