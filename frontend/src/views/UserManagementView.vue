<template>
  <div class="flex flex-col gap-4 sm:gap-6 lg:flex-1 lg:min-h-0">
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

    <!-- 清单卡：控制条、表头、行、分页同处一张卡，用发丝线分区，
         而不是「工具栏一张卡 + 列表一张卡」两张等重视觉块堆叠。
         静默刷新期旧数据原地保留，仅整卡降透明并暂停交互（无感换新，不整块替换） -->
    <div
      class="dash-card flex flex-col overflow-hidden transition-opacity lg:min-h-[260px] lg:flex-1 sm:min-h-0"
      :class="refreshing && 'opacity-60 pointer-events-none'"
    >
      <!-- 控制条：底色取页面表面色，让它在白卡上"切"出一条控制台；
           搜索 / 分段筛选 / 结果读数 / 刷新 / 新增 同处一行，桌面端与列表共宽 -->
      <div class="flex flex-col gap-2.5 border-b border-ink/5 bg-cloud/50 px-3 py-3 sm:flex-row sm:items-center sm:gap-3 sm:px-4">
        <div class="relative w-full min-w-0 sm:max-w-[20rem]">
          <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input
            v-model="keyword"
            type="text"
            autocomplete="off"
            enterkeyhint="search"
            aria-label="搜索用户名"
            placeholder="搜索用户名…"
            class="h-9 w-full rounded-xl border border-ink/10 bg-elevated pl-9 pr-8 text-sm text-ink outline-none transition placeholder:text-ink-muted focus:border-brand focus:ring-4 focus:ring-brand/10 sm:h-10"
            @input="store.onKeywordInput"
          />
          <button
            v-if="keyword"
            type="button"
            class="absolute right-1.5 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
            aria-label="清除搜索"
            @click="clearKeyword"
          >
            <Icon name="close" :size="14" />
          </button>
        </div>

        <!-- 移动端：筛选与操作折行成一条；桌面端拆开与搜索同行（sm:contents 让包裹层不再产生盒子） -->
        <div class="flex items-center gap-2 sm:contents">
          <!-- 角色只有三个互斥项，用分段控件取代下拉：少一层点击 -->
          <div class="inline-flex h-9 shrink-0 items-center gap-0.5 rounded-xl bg-ink/5 p-0.5 sm:h-10" role="tablist" aria-label="按角色筛选">
            <button
              v-for="opt in roleOptions"
              :key="opt.value"
              type="button"
              role="tab"
              :aria-selected="roleFilter === opt.value"
              class="h-full rounded-[10px] px-2.5 text-xs font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
              :class="roleFilter === opt.value ? 'bg-elevated text-ink shadow-sm ring-1 ring-ink/5' : 'text-ink-muted hover:text-ink'"
              @click="setRole(opt.value)"
            >
              {{ opt.label }}
            </button>
          </div>

          <span class="hidden shrink-0 text-xs tabular-nums text-ink-muted sm:inline sm:ml-auto">
            共 {{ displayTotal }} 位用户
          </span>

          <div class="ml-auto flex shrink-0 items-center gap-2 sm:ml-0">
            <button
              type="button"
              class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-ink/10 bg-elevated text-ink-muted transition hover:border-brand/30 hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30 disabled:opacity-50 sm:h-10 sm:w-10"
              aria-label="刷新"
              :disabled="loading"
              @click="refresh"
            >
              <Icon name="refresh" :size="17" :class="loading && 'spin-refresh'" />
            </button>
            <button
              type="button"
              class="inline-flex h-9 items-center justify-center gap-1.5 rounded-xl bg-brand px-3 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand/30 sm:h-10 sm:px-4"
              @click="store.openAdd"
            >
              <Icon name="plus" :size="17" />
              <span class="hidden sm:inline">新增用户</span>
              <span class="sm:hidden">新增</span>
            </button>
          </div>
        </div>
      </div>

      <!-- 首载占位：居中提示即可，卡片已由 min-height 锁高，不产生跳动 -->
      <div v-if="loading" class="flex flex-1 items-center justify-center gap-2 py-16 text-sm text-ink-muted">
        <Icon name="refresh" :size="16" class="spin-refresh text-brand" />
        <span>正在加载用户…</span>
      </div>

      <!-- 空状态：说明原因并给出下一步，而不是只报一句"暂无数据" -->
      <div v-else-if="rows.length === 0" class="flex flex-1 flex-col items-center justify-center gap-3 px-4 py-14 text-center">
        <span class="grid h-12 w-12 place-items-center rounded-2xl bg-cloud text-ink-muted">
          <Icon :name="hasFilter ? 'search' : 'users'" :size="22" />
        </span>
        <div class="space-y-1">
          <p class="text-sm font-medium text-ink">{{ hasFilter ? '没有匹配的用户' : '还没有用户' }}</p>
          <p class="text-xs text-ink-muted">{{ hasFilter ? '换个关键词或角色再试试。' : '点击右上角「新增用户」创建第一个账号。' }}</p>
        </div>
        <button
          v-if="hasFilter"
          type="button"
          class="mt-1 inline-flex h-8 items-center rounded-lg border border-ink/10 px-3 text-xs font-medium text-ink-soft transition hover:bg-cloud hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
          @click="clearFilters"
        >
          清除筛选条件
        </button>
      </div>

      <template v-else>
        <!-- 桌面表格（≥1024px）：表头固定、列宽对齐 -->
        <div class="xb-scroll hidden min-h-0 flex-1 overflow-auto lg:block">
          <table class="w-full table-fixed text-left text-sm">
          <colgroup>
            <col class="w-[20%]" />
            <col class="w-[13%]" />
            <col class="w-[11%]" />
            <col class="w-[24%]" />
            <col class="w-[16%]" />
            <col class="w-[16%]" />
          </colgroup>
          <thead>
            <tr class="border-b border-ink/10 text-ink-muted">
              <th class="sticky top-0 z-10 bg-elevated px-3 py-2.5 align-middle font-medium whitespace-nowrap">用户</th>
              <th class="sticky top-0 z-10 bg-elevated px-3 py-2.5 align-middle font-medium whitespace-nowrap">角色</th>
              <th class="sticky top-0 z-10 bg-elevated px-3 py-2.5 align-middle font-medium whitespace-nowrap">状态</th>
              <th class="sticky top-0 z-10 bg-elevated px-3 py-2.5 align-middle font-medium whitespace-nowrap">额度（已用 / 总额）</th>
              <th class="sticky top-0 z-10 bg-elevated px-3 py-2.5 align-middle font-medium whitespace-nowrap">创建时间</th>
              <th class="sticky top-0 z-10 bg-elevated pl-5 pr-3 py-2.5 align-middle text-left font-medium whitespace-nowrap">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in rows"
              :key="item.user_id"
              class="group border-b border-ink/5 transition-colors last:border-0 hover:bg-cloud/40"
            >
              <!-- 用户 -->
              <td class="relative px-3 py-2.5 align-middle">
                <!-- 悬停导轨：贴在行左缘的色条，快速定位当前行，不参与布局 -->
                <span class="xb-rail pointer-events-none absolute inset-y-0 left-0 w-[3px] bg-brand opacity-0 transition-opacity group-hover:opacity-100" aria-hidden="true" />
                <div class="flex items-center gap-3">
                  <span class="grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-semibold ring-1 ring-inset ring-ink/5" :class="avatarClass(item.username)">
                    {{ initial(item.username) }}
                  </span>
                  <span class="truncate font-medium text-ink" v-html="highlight(item.username)"></span>
                </div>
              </td>
              <!-- 角色 -->
              <td class="px-3 py-2.5 align-middle">
                <span
                  class="inline-flex items-center gap-1.5 whitespace-nowrap text-[13px] font-medium"
                  :class="item.role === 'admin' ? 'text-brand' : 'text-ink-muted'"
                >
                  <Icon :name="item.role === 'admin' ? 'shield' : 'user'" :size="14" />
                  {{ item.role === 'admin' ? '管理员' : '普通用户' }}
                </span>
              </td>
              <!-- 状态 -->
              <td class="px-3 py-2.5 align-middle">
                <span
                  class="inline-flex items-center gap-1.5 whitespace-nowrap text-[13px] font-medium"
                  :class="item.enabled ? 'text-success' : 'text-danger'"
                >
                  <span class="h-1.5 w-1.5 rounded-full" :class="item.enabled ? 'bg-success' : 'bg-danger'" />
                  {{ item.enabled ? '启用' : '禁用' }}
                </span>
              </td>
              <!-- 额度 -->
              <td class="px-3 py-2.5 align-middle whitespace-nowrap">
                <div class="w-full">
                  <div class="mb-1 flex items-baseline justify-between gap-2 text-xs">
                    <span class="tabular-nums text-ink-muted">{{ item.used_quota }} / {{ item.quota }}</span>
                    <span class="font-semibold tabular-nums" :class="quotaTextClass(item)">{{ usagePercent(item) }}%</span>
                  </div>
                  <div class="relative h-1.5 w-full overflow-hidden rounded-full bg-ink/10">
                    <div
                      class="xb-quota h-full rounded-full transition-all duration-500"
                      :class="quotaBarClass(item)"
                      :style="{ width: usagePercent(item) + '%' }"
                    />
                    <!-- 阈值刻度：70% 警戒 / 90% 危险。压在填充之上，越接近上限越显眼；
                         填充本身是实色令牌，故刻度在两态都用白线，不随明暗轴走 -->
                    <span class="pointer-events-none absolute inset-y-0 left-[70%] w-px bg-white/70" aria-hidden="true" />
                    <span class="pointer-events-none absolute inset-y-0 left-[90%] w-px bg-white/85" aria-hidden="true" />
                  </div>
                </div>
              </td>
              <td class="px-3 py-2.5 align-middle whitespace-nowrap text-[13px] text-ink-muted tabular-nums">{{ item.created_at }}</td>
              <!-- 操作：图标 + 文字，与账号管理页保持一致，左对齐 -->
              <td class="px-3 py-2.5 align-middle whitespace-nowrap">
                <div class="flex flex-nowrap items-center justify-start gap-0.5">
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1.5 text-[13px] font-medium text-brand transition hover:bg-brand/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
                    @click="store.openEdit(item)"
                  >
                    <Icon name="edit" :size="14" />编辑
                  </button>
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1.5 text-[13px] font-medium text-ink-muted transition hover:bg-cloud focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
                    :class="item.enabled ? 'hover:text-warning' : 'hover:text-success'"
                    @click="onToggle(item)"
                  >
                    <Icon :name="item.enabled ? 'x-circle' : 'check-circle'" :size="14" />{{ item.enabled ? '禁用' : '启用' }}
                  </button>
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1.5 text-[13px] font-medium text-danger transition hover:bg-danger/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/30"
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
      <div class="xb-scroll overflow-auto lg:hidden lg:flex-1 lg:min-h-0">
        <div class="space-y-3 p-3">
          <div
            v-for="item in rows"
            :key="item.user_id"
            v-reveal
            class="rounded-xl border border-ink/5 bg-card p-3"
          >
            <div class="flex items-center gap-3">
              <span class="grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-semibold ring-1 ring-inset ring-ink/5" :class="avatarClass(item.username)">
                {{ initial(item.username) }}
              </span>
              <span class="min-w-0 flex-1 truncate font-medium text-ink" v-html="highlight(item.username)"></span>
              <span class="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap text-[13px] font-medium" :class="item.enabled ? 'text-success' : 'text-danger'">
                <span class="h-1.5 w-1.5 rounded-full" :class="item.enabled ? 'bg-success' : 'bg-danger'" />
                {{ item.enabled ? '启用' : '禁用' }}
              </span>
            </div>
            <div class="mt-2.5 flex items-center gap-2 text-xs">
              <span class="inline-flex items-center gap-1.5 whitespace-nowrap font-medium" :class="item.role === 'admin' ? 'text-brand' : 'text-ink-muted'">
                <Icon :name="item.role === 'admin' ? 'shield' : 'user'" :size="14" />
                {{ item.role === 'admin' ? '管理员' : '普通用户' }}
              </span>
              <span class="tabular-nums text-ink-muted">额度 {{ item.used_quota }} / {{ item.quota }}</span>
              <span class="ml-auto font-semibold tabular-nums" :class="quotaTextClass(item)">{{ usagePercent(item) }}%</span>
            </div>
            <div class="relative mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-ink/10">
              <div
                class="xb-quota h-full rounded-full transition-all duration-500"
                :class="quotaBarClass(item)"
                :style="{ width: usagePercent(item) + '%' }"
              />
              <span class="pointer-events-none absolute inset-y-0 left-[70%] w-px bg-white/70" aria-hidden="true" />
              <span class="pointer-events-none absolute inset-y-0 left-[90%] w-px bg-white/85" aria-hidden="true" />
            </div>
            <div class="mt-2 text-xs text-ink-muted tabular-nums">创建于 {{ item.created_at }}</div>
            <div class="mt-3 flex gap-2 border-t border-ink/5 pt-3">
              <button
                type="button"
                class="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-ink/10 py-2 text-sm font-medium text-ink-soft transition hover:bg-cloud hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
                @click="store.openEdit(item)"
              >
                <Icon name="edit" :size="16" /> 编辑
              </button>
              <button
                type="button"
                class="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-ink/10 py-2 text-sm font-medium text-ink-soft transition hover:bg-cloud focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
                :class="item.enabled ? 'hover:text-warning' : 'hover:text-success'"
                @click="onToggle(item)"
              >
                <Icon :name="item.enabled ? 'x-circle' : 'check-circle'" :size="16" /> {{ item.enabled ? '禁用' : '启用' }}
              </button>
              <button
                type="button"
                class="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-ink/10 py-2 text-sm font-medium text-ink-soft transition hover:bg-danger/10 hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/30"
                @click="store.openDelete(item)"
              >
                <Icon name="trash" :size="16" /> 删除
              </button>
            </div>
          </div>
        </div>
      </div>
      </template>

      <!-- 分页 -->
      <div v-if="!loading && rows.length" class="shrink-0 border-t border-ink/5 px-3 py-2.5 sm:px-4">
        <BasePagination
          :page="page"
          :page-size="pageSize"
          :total="displayTotal"
          :page-size-options="[10, 20, 50]"
          :disabled="loading"
          show-jump
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

    <!-- 底部间距占位：真实在流子元素，盒高计入 scrollHeight，不受滚动容器末端 padding/margin 折叠影响；
         -mt-4 sm:-mt-6 抵消根容器 gap-4 sm:gap-6，确保底部间距精确 24px、与其它页面一致 -->
    <div class="h-6 shrink-0 -mt-4 sm:-mt-6" aria-hidden="true"></div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import StatCard from '@/components/StatCard.vue'
import BasePagination from '@/components/BasePagination.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import UserFormModal from '@/components/UserFormModal.vue'
import Icon from '@/components/Icon.vue'
import { useUsersStore } from '@/stores/users'
import { toast } from '@/utils/toast'
import { storeToRefs } from 'pinia'

// 领域状态下沉到 store：视图只做渲染、展示辅助与 toast 提示
const store = useUsersStore()
const {
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
  deleting,
  rows,
  displayTotal,
  quotaRate
} = storeToRefs(store)

// 提示口径：成功/自定义文案用全局 toast 就地展示；接口失败由 request.js 统一 toast，
// 本视图的 catch 只吞掉 rejection（避免未处理 Promise 告警），不再重复提示

// 删除确认文案：物理删除会连带清掉该用户名下的账号、任务与记录，代价必须写出来
const deleteMessage = computed(() => {
  const u = store.deletingUser
  if (!u?.username) return ''
  const accs = u.used_quota || 0
  const cascade = accs
    ? `将同时删除其 ${accs} 个 B 平台账号，以及这些账号下的定时任务、签到记录与推送日志。`
    : '该用户名下没有 B 平台账号，仅删除账号本身。'
  return `确定要删除用户「${u.username}」吗？${cascade}此操作不可恢复。`
})

// 角色筛选：三项互斥，用分段控件承载；写回 store 的 roleFilter 后统一走 onFilterChange 重置页码
const roleOptions = [
  { value: '', label: '全部' },
  { value: 'admin', label: '管理员' },
  { value: 'user', label: '普通用户' }
]
function setRole(value) {
  if (roleFilter.value === value) return
  roleFilter.value = value
  store.onFilterChange()
}

const hasFilter = computed(() => !!keyword.value.trim() || !!roleFilter.value)
function clearKeyword() {
  keyword.value = ''
  store.onFilterChange()
}
function clearFilters() {
  keyword.value = ''
  roleFilter.value = ''
  store.onFilterChange()
}

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

// 关键词高亮：命中片段包一层 mark（与账号树页同一套做法）。
// 用户名来自接口，转义后再拼接，避免 v-html 注入
const ESCAPE_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ESCAPE_MAP[c])
}
function highlight(name) {
  const text = String(name ?? '')
  const kw = keyword.value.trim()
  if (!kw) return escapeHtml(text)
  const i = text.toLowerCase().indexOf(kw.toLowerCase())
  if (i < 0) return escapeHtml(text)
  const hit = escapeHtml(text.slice(i, i + kw.length))
  return `${escapeHtml(text.slice(0, i))}<mark class="rounded bg-amber/30 px-0.5 text-ink">${hit}</mark>${escapeHtml(text.slice(i + kw.length))}`
}

// 事件包装：调用 store action 并负责 toast 反馈
function refresh() {
  store.fetchUsers().catch(() => {})
}
async function onToggle(item) {
  const next = !item.enabled
  try {
    await store.toggleStatus(item)
    toast(next ? '已启用该用户' : '已禁用该用户', 'success')
  } catch {
    /* 失败已由 request.js 全局 toast */
  }
}
async function onConfirmDelete() {
  const name = store.deletingUser?.username
  try {
    await store.confirmDelete()
    toast(`已删除用户「${name}」`, 'success')
  } catch {
    /* 失败已由 request.js 全局 toast */
  }
}
async function onSubmit(payload) {
  try {
    await store.handleFormSubmit(payload)
    toast(store.formMode === 'add' ? '用户创建成功' : '保存成功', 'success')
  } catch {
    /* 失败已由 request.js 全局 toast */
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
  /* 悬停导轨与额度填充的过渡关掉，避免系统级减弱动效偏好下仍有位移/渐变 */
  .xb-rail, .xb-quota { transition: none; }
}
</style>
