<template>
  <div class="flex flex-1 min-h-0 flex-col gap-4 sm:gap-6">
    <!-- 汇总卡片：移动端紧凑，避免挤压下方列表 -->
    <div class="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
      <StatCard label="用户总数" :value="summary.total_users" icon="users" tone="brand" delay="1" compact :loading="loading" />
      <StatCard label="启用中" :value="summary.enabled" icon="check-circle" tone="success" delay="2" compact :loading="loading" />
      <StatCard label="已禁用" :value="summary.disabled" icon="x-circle" tone="danger" delay="3" compact :loading="loading" />
      <StatCard
        label="额度使用率"
        :value="quotaRate"
        unit="%"
        icon="user"
        :tone="quotaRate >= 90 ? 'danger' : quotaRate >= 70 ? 'warning' : 'brand'"
        :delta="`${summary.used_quota} / ${summary.total_quota}`"
        delta-type="flat"
        delta-hint="已用 / 总"
        delay="4"
        compact
        :loading="loading"
      />
    </div>

    <!-- 工具栏：移动端紧凑一行布局（搜索 + 筛选/刷新/新增），PC 横向 -->
    <div class="dash-card fade-up flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:gap-3 sm:p-4">
      <div class="relative w-full min-w-0 flex-1">
        <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
        <input
          v-model="keyword"
          type="text"
          placeholder="搜索用户名…"
          class="login-input h-9 py-0 pl-9 text-sm sm:h-11"
          @input="store.onKeywordInput"
        />
      </div>
      <div class="flex shrink-0 items-center gap-2 sm:gap-3">
        <div class="w-36 shrink-0 sm:w-40">
          <BaseSelect
            v-model="roleFilter"
            placeholder="全部角色"
            :options="[{ label: '全部用户', value: '' }, { label: '管理员', value: 'admin' }, { label: '普通用户', value: 'user' }]"
            @update:model-value="store.onFilterChange"
          />
        </div>
        <button
          type="button"
          class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-ink/10 text-ink-muted transition hover:bg-cloud hover:text-ink sm:h-11 sm:w-11"
          aria-label="刷新"
          :disabled="loading"
          @click="refresh"
        >
          <Icon name="refresh" :size="17" :class="loading && 'spin-refresh'" />
        </button>
        <button
          type="button"
          class="inline-flex h-9 items-center justify-center gap-1.5 rounded-xl bg-brand px-3 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark focus:outline-none focus:ring-4 focus:ring-brand/30 sm:w-auto sm:px-4 sm:py-2.5"
          @click="store.openAdd"
        >
          <Icon name="plus" :size="17" />
          <span class="hidden sm:inline">新增用户</span>
          <span class="sm:hidden">新增</span>
        </button>
      </div>
    </div>

    <!-- 用户列表：桌面用表格（表头固定、列对齐），移动端用卡片，页面主体高度固定 -->
    <div class="dash-card flex min-h-[260px] flex-1 flex-col overflow-hidden sm:min-h-0">
      <!-- 加载中 -->
      <div v-if="loading" class="flex flex-1 items-center justify-center text-sm text-ink-muted">加载中…</div>
      <!-- 空状态 -->
      <div v-else-if="rows.length === 0" class="flex flex-1 flex-col items-center justify-center gap-2 px-4 text-center text-ink-muted">
        <Icon name="users" :size="28" class="opacity-50" />
        <span>暂无用户，调整筛选条件或点击「新增用户」。</span>
      </div>
      <template v-else>
        <!-- 桌面表格（≥1024px）：表头固定、列宽对齐 -->
        <div class="xb-scroll hidden min-h-0 flex-1 overflow-auto lg:block">
          <table class="w-full table-fixed text-left text-sm">
          <colgroup>
            <col class="w-[15%]" />
            <col class="w-[12%]" />
            <col class="w-[11%]" />
            <col class="w-[28%]" />
            <col class="w-[18%]" />
            <col class="w-[16%]" />
          </colgroup>
          <thead>
            <tr class="border-b border-ink/10 text-ink-muted">
              <th class="sticky top-0 z-10 bg-white px-3 py-2.5 align-middle font-medium whitespace-nowrap">用户</th>
              <th class="sticky top-0 z-10 bg-white px-3 py-2.5 align-middle font-medium whitespace-nowrap">角色</th>
              <th class="sticky top-0 z-10 bg-white px-3 py-2.5 align-middle font-medium whitespace-nowrap">状态</th>
              <th class="sticky top-0 z-10 bg-white px-3 py-2.5 align-middle font-medium whitespace-nowrap">额度（已用 / 总额）</th>
              <th class="sticky top-0 z-10 bg-white px-3 py-2.5 align-middle font-medium whitespace-nowrap">创建时间</th>
              <th class="sticky top-0 z-10 bg-white pl-5 pr-3 py-2.5 align-middle text-left font-medium whitespace-nowrap">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in rows"
              :key="item.user_id"
              class="border-b border-ink/5 transition last:border-0 hover:bg-cloud/40"
            >
              <!-- 用户 -->
              <td class="px-3 py-2.5 align-middle">
                <div class="flex items-center gap-3">
                  <span class="grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-semibold" :class="avatarClass(item.username)">
                    {{ initial(item.username) }}
                  </span>
                  <span class="truncate font-medium text-ink">{{ item.username }}</span>
                </div>
              </td>
              <!-- 角色 -->
              <td class="px-3 py-2.5 align-middle">
                <span class="inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-1 text-xs font-medium" :class="item.role === 'admin' ? 'bg-brand/10 text-brand' : 'bg-ink/5 text-ink-soft'">
                  <Icon :name="item.role === 'admin' ? 'shield' : 'user'" :size="13" />
                  {{ item.role === 'admin' ? '管理员' : '普通用户' }}
                </span>
              </td>
              <!-- 状态 -->
              <td class="px-3 py-2.5 align-middle">
                <span class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-1 text-xs font-medium" :class="item.enabled ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'">
                  <span class="h-1.5 w-1.5 rounded-full" :class="item.enabled ? 'bg-success' : 'bg-danger'" />
                  {{ item.enabled ? '启用' : '禁用' }}
                </span>
              </td>
              <!-- 额度 -->
              <td class="px-3 py-2.5 align-middle whitespace-nowrap">
                <div class="w-full">
                  <div class="mb-1 flex items-center justify-between text-xs text-ink-muted">
                    <span class="tabular-nums">{{ item.used_quota }} / {{ item.quota }}</span>
                    <span class="font-medium tabular-nums" :class="quotaTextClass(item)">{{ usagePercent(item) }}%</span>
                  </div>
                  <div class="h-1.5 w-full overflow-hidden rounded-full bg-ink/10">
                    <div class="h-full rounded-full transition-all duration-500" :class="quotaBarClass(item)" :style="{ width: usagePercent(item) + '%' }" />
                  </div>
                </div>
              </td>
              <td class="px-3 py-2.5 align-middle whitespace-nowrap text-ink-muted tabular-nums">{{ item.created_at }}</td>
              <!-- 操作：图标 + 文字，与账号管理页保持一致，左对齐 -->
              <td class="px-3 py-2.5 align-middle whitespace-nowrap">
                <div class="flex flex-nowrap items-center justify-start gap-1">
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1.5 text-[13px] font-medium text-brand transition hover:bg-brand/10"
                    @click="store.openEdit(item)"
                  >
                    <Icon name="edit" :size="14" />编辑
                  </button>
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1.5 text-[13px] font-medium text-ink-muted transition hover:bg-cloud"
                    :class="item.enabled ? 'hover:text-warning' : 'hover:text-success'"
                    @click="onToggle(item)"
                  >
                    <Icon :name="item.enabled ? 'x-circle' : 'check-circle'" :size="14" />{{ item.enabled ? '禁用' : '启用' }}
                  </button>
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1.5 text-[13px] font-medium text-danger transition hover:bg-danger/10"
                    @click="store.openDelete(item)"
                  >
                    <Icon name="trash" :size="14" />删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 移动端卡片列表（<1024px）：无横向溢出、操作便捷 -->
      <div class="xb-scroll min-h-0 flex-1 overflow-auto lg:hidden">
        <div class="space-y-3 p-3">
          <div
            v-for="item in rows"
            :key="item.user_id"
            class="rounded-xl border border-ink/10 bg-white p-3"
          >
            <div class="flex items-center gap-3">
              <span class="grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-semibold" :class="avatarClass(item.username)">
                {{ initial(item.username) }}
              </span>
              <span class="min-w-0 flex-1 truncate font-medium text-ink">{{ item.username }}</span>
              <span class="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-1 text-xs font-medium" :class="item.enabled ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'">
                <span class="h-1.5 w-1.5 rounded-full" :class="item.enabled ? 'bg-success' : 'bg-danger'" />
                {{ item.enabled ? '启用' : '禁用' }}
              </span>
            </div>
            <div class="mt-2.5 flex items-center gap-2 text-xs text-ink-soft">
              <span class="inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-1 font-medium" :class="item.role === 'admin' ? 'bg-brand/10 text-brand' : 'bg-ink/5 text-ink-soft'">
                <Icon :name="item.role === 'admin' ? 'shield' : 'user'" :size="13" />
                {{ item.role === 'admin' ? '管理员' : '普通用户' }}
              </span>
              <span class="tabular-nums text-ink-muted">额度 {{ item.used_quota }} / {{ item.quota }}</span>
              <span class="ml-auto font-medium tabular-nums" :class="quotaTextClass(item)">{{ usagePercent(item) }}%</span>
            </div>
            <div class="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-ink/10">
              <div class="h-full rounded-full transition-all duration-500" :class="quotaBarClass(item)" :style="{ width: usagePercent(item) + '%' }" />
            </div>
            <div class="mt-2 text-xs text-ink-muted tabular-nums">创建于 {{ item.created_at }}</div>
            <div class="mt-3 flex gap-2 border-t border-ink/5 pt-3">
              <button type="button" class="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-ink/10 py-2 text-sm font-medium text-ink-soft transition hover:bg-cloud hover:text-brand" @click="store.openEdit(item)">
                <Icon name="edit" :size="16" /> 编辑
              </button>
              <button type="button" class="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-ink/10 py-2 text-sm font-medium transition" :class="item.enabled ? 'text-ink-soft hover:bg-cloud hover:text-warning' : 'text-ink-soft hover:bg-cloud hover:text-success'" @click="onToggle(item)">
                <Icon :name="item.enabled ? 'x-circle' : 'check-circle'" :size="16" /> {{ item.enabled ? '禁用' : '启用' }}
              </button>
              <button type="button" class="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-ink/10 py-2 text-sm font-medium text-ink-soft transition hover:bg-danger/10 hover:text-danger" @click="store.openDelete(item)">
                <Icon name="trash" :size="16" /> 删除
              </button>
            </div>
          </div>
        </div>
      </div>
      </template>

      <!-- 分页 -->
      <div v-if="!loading && rows.length" class="shrink-0 border-t border-ink/5 px-3 py-2">
        <Pagination
          :page="page"
          :page-size="pageSize"
          :total="displayTotal"
          :page-size-options="[10, 20, 50]"
          :disabled="loading"
          @update:page="store.onPageChange"
          @update:page-size="store.onPageSizeChange"
        />
      </div>
    </div>

    <!-- 新增 / 编辑弹窗 -->
    <UserFormModal
      v-model="showForm"
      :mode="formMode"
      :user="editingUser"
      :submitting="formSubmitting"
      @submit="onSubmit"
      @cancel="store.closeForm"
    />

    <!-- 删除二次确认 -->
    <ConfirmModal
      v-model="showDelete"
      title="删除用户"
      :message="deleteMessage"
      icon="trash"
      danger
      confirm-text="删除"
      :confirming="deleting"
      confirming-text="删除中…"
      @confirm="onConfirmDelete"
      @cancel="store.closeDelete"
    />

    <!-- 轻量提示：右下角深色底，样式收敛到共享组件 PageToast（与系统设置页同一出口） -->
    <PageToast :show="toast.show" :message="toast.message" :type="toast.type" />

    <!-- 底部间距占位：真实在流子元素，盒高计入 scrollHeight，不受滚动容器末端 padding/margin 折叠影响；
         -mt-4 sm:-mt-6 抵消根容器 gap-4 sm:gap-6，确保底部间距精确 24px、与其它页面一致 -->
    <div class="h-6 shrink-0 -mt-4 sm:-mt-6" aria-hidden="true"></div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'
import StatCard from '@/components/StatCard.vue'
import Pagination from '@/components/Pagination.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import UserFormModal from '@/components/UserFormModal.vue'
import Icon from '@/components/Icon.vue'
import PageToast from '@/components/PageToast.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import { useUsersStore } from '@/stores/users'
import { storeToRefs } from 'pinia'

// 领域状态下沉到 store：视图只做渲染、展示辅助与 toast 提示
const store = useUsersStore()
const {
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
  quotaRate
} = storeToRefs(store)

// 轻量提示
const toast = reactive({ show: false, message: '', type: 'success' })
let toastTimer = null
function showToast(message, type = 'success') {
  toast.message = message
  toast.type = type
  toast.show = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.show = false), 2600)
}

// 删除确认文案
const deleteMessage = computed(() =>
  store.deletingUser?.username
    ? `确定要删除用户「${store.deletingUser.username}」吗？此操作不可恢复。`
    : ''
)

// 头像 / 额度展示辅助
const avatarPalette = ['bg-brand/15 text-brand', 'bg-success/15 text-success', 'bg-amber/15 text-amber', 'bg-info/15 text-info', 'bg-danger/15 text-danger']
function avatarClass(name) {
  let h = 0
  for (const ch of name || '') h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return avatarPalette[h % avatarPalette.length]
}
function initial(name) {
  return (name || '?').trim().charAt(0).toUpperCase()
}
function usagePercent(item) {
  return item.quota > 0 ? Math.min(100, Math.round((item.used_quota / item.quota) * 100)) : 0
}
function quotaBarClass(item) {
  const p = usagePercent(item)
  return p >= 90 ? 'bg-danger' : p >= 70 ? 'bg-warning' : 'bg-brand'
}
function quotaTextClass(item) {
  const p = usagePercent(item)
  return p >= 90 ? 'text-danger' : p >= 70 ? 'text-warning' : 'text-ink-muted'
}

// 事件包装：调用 store action 并负责 toast 反馈
function refresh() {
  store.fetchUsers().catch((e) => showToast(e.message || '获取用户列表失败', 'error'))
}
async function onToggle(item) {
  const next = !item.enabled
  try {
    await store.toggleStatus(item)
    showToast(next ? '已启用该用户' : '已禁用该用户', 'success')
  } catch (e) {
    showToast(e.message || '状态更新失败', 'error')
  }
}
async function onConfirmDelete() {
  const name = store.deletingUser?.username
  try {
    await store.confirmDelete()
    showToast(`已删除用户「${name}」`, 'success')
  } catch (e) {
    showToast(e.message || '删除失败', 'error')
  }
}
async function onSubmit(payload) {
  try {
    await store.handleFormSubmit(payload)
    showToast(store.formMode === 'add' ? '用户创建成功' : '保存成功', 'success')
  } catch (e) {
    showToast(e.message || '操作失败', 'error')
  }
}

onMounted(refresh)
</script>

<style scoped>
/* 纵向滚动时预留滚动条宽度，避免 thead 与 tbody 右列因滚动条占位而错位 */
.xb-scroll { scrollbar-gutter: stable; }
/* 仅让刷新图标旋转，按钮容器与其它元素保持静止 */
.spin-refresh { animation: xb-spin 0.8s linear infinite; }
@keyframes xb-spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
  .spin-refresh { animation: none; }
}
</style>
