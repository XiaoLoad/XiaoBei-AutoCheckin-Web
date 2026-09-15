<template>
  <!-- 根容器：占满父级高度，列表卡片 flex-1 内部滚动，解决高度过低问题 -->
  <div class="flex flex-col gap-6 lg:flex-1 lg:min-h-0">
    <!-- 统一操作栏：搜索 + 筛选 + 刷新 + 重置 + 新增，合并为一卡，简约单行布局。
         relative z-30 提升堆叠层级，确保内部下拉面板不被下方列表卡片遮挡。 -->
    <div class="dash-card fade-up relative z-30 shrink-0 p-3 sm:p-4">
      <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
        <!-- 搜索框：进一步加宽，提升输入体验与整体美观 -->
        <div class="relative w-full sm:w-80">
          <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input
            v-model="keyword"
            type="text"
            placeholder="搜索账号 / 姓名 / 学号"
            class="login-input py-2 pl-9 text-sm"
          />
        </div>

        <!-- 分隔线：区分搜索区与筛选区 -->
        <span class="hidden h-6 w-px bg-ink/10 sm:block" />

        <!-- 筛选组：标签改为醒目文字、下拉框采用紧凑尺寸，比例协调 -->
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div class="flex items-center gap-2">
            <span class="shrink-0 text-sm font-medium text-ink-soft">签到类型</span>
            <div class="w-28">
              <BaseSelect v-model="typeFilter" :options="typeOptions" placeholder="全部" size="sm" />
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span class="shrink-0 text-sm font-medium text-ink-soft">签到状态</span>
            <div class="w-28">
              <BaseSelect v-model="signFilter" :options="signOptions" placeholder="全部" size="sm" />
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span class="shrink-0 text-sm font-medium text-ink-soft">启用状态</span>
            <div class="w-24">
              <BaseSelect v-model="enabledFilter" :options="enabledOptions" placeholder="全部" size="sm" />
            </div>
          </div>
        </div>

        <!-- 右侧操作：刷新 / 重置（有筛选时显示）/ 新增 -->
        <div class="ml-auto flex items-center gap-2">
          <button
            type="button"
            class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-ink/10 text-ink-muted transition hover:bg-cloud hover:text-ink"
            aria-label="刷新"
            :disabled="loading"
            @click="refresh"
          >
            <Icon name="refresh" :size="17" :class="loading && 'spin-refresh'" />
          </button>
          <button
            v-if="hasFilter"
            type="button"
            class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-ink/10 px-3 text-sm font-medium text-ink-soft transition hover:bg-cloud"
            @click="store.resetFilters"
          >
            <Icon name="close" :size="14" />重置
          </button>
          <button
            type="button"
            class="inline-flex items-center justify-center gap-1.5 rounded-xl bg-brand px-3.5 py-2 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark focus:outline-none focus:ring-4 focus:ring-brand/30 sm:px-4"
            @click="store.openAdd"
          >
            <Icon name="plus" :size="17" />
            <span class="hidden sm:inline">新增账号</span>
            <span class="sm:hidden">新增</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 列表卡片：账号卡片网格（桌面/移动同一套），卡片 flex-1 内部滚动，底部固定分页。
         静默刷新期旧数据原地保留，仅整卡降透明并暂停交互 -->
    <div
      class="dash-card fade-up flex flex-col overflow-hidden rounded-2xl transition-opacity lg:flex-1 lg:min-h-0"
      :class="refreshing && 'opacity-60 pointer-events-none'"
    >
      <!-- 加载态 -->
      <div v-if="loading" class="flex flex-1 items-center justify-center text-sm text-ink-muted">加载中…</div>

      <!-- 空状态：铺满容器垂直水平居中 -->
      <div v-else-if="filtered.length === 0" class="flex flex-1 flex-col items-center justify-center gap-2 px-4 text-center text-sm text-ink-muted">
        <Icon name="user" :size="28" class="opacity-50" />
        <span>暂无账号，点击「新增账号」添加你的第一个 B 平台账号。</span>
      </div>

      <!-- 账号卡片网格：1 列（小屏）/ 2 列（sm）/ 3 列（xl） -->
      <div v-else class="xb-scroll overflow-auto p-3 sm:p-4 lg:flex-1 lg:min-h-0">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <article
            v-for="item in pagedRows"
            :key="item.id"
            v-reveal
            class="flex flex-col rounded-xl border border-ink/10 bg-card p-4 transition hover:border-brand/40"
          >
            <!-- 头部：头像（圆环色=上次签到状态）+ 姓名/账号 + 启用状态 -->
            <div class="flex items-center gap-3">
              <div class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand/10 text-sm font-medium text-brand ring-2" :class="ringCls(item)">
                {{ avatarChar(item) }}
              </div>
              <div class="min-w-0 flex-1">
                <p class="break-words text-sm font-medium text-ink">{{ (item.profile && item.profile.name) || '未命名' }}</p>
                <p class="mt-0.5 break-all text-xs text-ink-muted">{{ item.account }}</p>
              </div>
              <span class="inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium" :class="item.enabled ? 'bg-success/10 text-success' : 'bg-ink/5 text-ink-muted'">
                <span class="h-1.5 w-1.5 rounded-full" :class="item.enabled ? 'bg-success' : 'bg-ink/30'" />
                {{ item.enabled ? '启用' : '禁用' }}
              </span>
            </div>

            <!-- 字段清单：标签 + 完整值（items-baseline 保证标签与值首行文字基线对齐；值允许换行，不截断） -->
            <dl class="mt-3 space-y-2 border-t border-ink/5 pt-3 text-xs">
              <div class="flex items-baseline gap-2">
                <dt class="w-16 shrink-0 leading-5 text-ink-muted">学号</dt>
                <dd class="min-w-0 flex-1 break-words leading-5 tabular-nums text-ink-soft">{{ (item.profile && item.profile.studentNo) || '—' }}</dd>
              </div>
              <div class="flex items-baseline gap-2">
                <dt class="w-16 shrink-0 leading-5 text-ink-muted">院系班级</dt>
                <dd class="min-w-0 flex-1 break-words leading-5 text-ink-soft">{{ deptText(item) || '登录后自动获取' }}</dd>
              </div>
              <div class="flex items-baseline gap-2">
                <dt class="w-16 shrink-0 leading-5 text-ink-muted">签到类型</dt>
                <dd class="min-w-0 flex-1 leading-5">
                  <span class="inline-flex items-center rounded-full px-2 py-0.5 font-medium" :class="typeMeta(item).cls">{{ typeMeta(item).label }}</span>
                </dd>
              </div>
              <div class="flex items-baseline gap-2">
                <dt class="w-16 shrink-0 leading-5 text-ink-muted">上次签到</dt>
                <dd class="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-1.5 gap-y-1 leading-5">
                  <span class="leading-5 tabular-nums text-ink-soft">{{ (item.lastSignIn && item.lastSignIn.time) || '—' }}</span>
                  <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium" :class="signMeta(item).tag">
                    <span class="h-1.5 w-1.5 rounded-full" :class="signMeta(item).dot" />{{ signMeta(item).label }}
                  </span>
                </dd>
              </div>
              <div class="flex items-baseline gap-2">
                <dt class="w-16 shrink-0 leading-5 text-ink-muted">推送凭证</dt>
                <dd class="flex min-w-0 flex-1 flex-wrap items-center gap-1 leading-5">
                  <template v-if="pushChannelsOf(item).length">
                    <span
                      v-for="ch in pushChannelsOf(item)"
                      :key="ch"
                      :title="pushChipTitle(item, ch)"
                      class="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 font-medium"
                      :class="pushChipCls(item, ch)"
                    >
                      <span class="h-1.5 w-1.5 rounded-full" :class="channelDot(ch)" />{{ channelLabel(ch) }}
                    </span>
                  </template>
                  <span v-else class="text-ink-muted">跟随配置套</span>
                </dd>
              </div>
            </dl>

            <!-- 操作行：右对齐 -->
            <div class="mt-2.5 flex items-center justify-end gap-1 border-t border-ink/5 pt-2">
              <button class="rounded-lg px-2.5 py-1.5 text-xs font-medium text-brand transition hover:bg-brand/10" @click="store.openEdit(item)">编辑</button>
              <button class="rounded-lg px-2.5 py-1.5 text-xs font-medium text-ink-muted transition hover:bg-cloud" @click="onToggle(item)">{{ item.enabled ? '禁用' : '启用' }}</button>
              <button class="rounded-lg px-2.5 py-1.5 text-xs font-medium text-danger transition hover:bg-danger/10" @click="store.askDelete(item)">删除</button>
            </div>
          </article>
        </div>
      </div>

      <!-- 分页（与用户管理页同一出口：BasePagination） -->
      <div v-if="!loading && filtered.length > 0" class="shrink-0 border-t border-ink/5 px-3 py-2">
        <BasePagination
          :page="page"
          :page-size="pageSize"
          :total="filtered.length"
          :page-size-options="[10, 20, 50]"
          :disabled="loading"
          show-jump
          @update:page="store.onPageChange"
          @update:page-size="store.onPageSizeChange"
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
      @cancel="store.closeForm"
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
      @confirm="onConfirmDelete"
      @cancel="store.closeDelete"
    />

    <!-- 底部间距占位：真实在流子元素，盒高计入 scrollHeight，不受滚动容器末端 padding/margin 折叠影响；
         -mt-6 抵消根容器 gap-6，确保底部间距精确 24px、与其它页面一致 -->
    <div class="h-6 shrink-0 -mt-6" aria-hidden="true"></div>
  </div>
</template>

<script setup>
import { useAccountsStore } from '@/stores/accounts'
import { storeToRefs } from 'pinia'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import BasePagination from '@/components/BasePagination.vue'
import AccountFormModal from '@/components/AccountFormModal.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import { activeChannels, channelDot, channelLabel, channelTone, readCredEntry } from '@/utils/pushChannels'

// 领域状态下沉到 store：视图只做渲染与展示辅助，数据编排由 store 负责
const store = useAccountsStore()
const {
  loading,
  refreshing,
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
  pagedRows
} = storeToRefs(store)

// 事件包装：失败时 rejection 已由 request.js 全局 toast 提示，这里吞掉避免未处理告警
function refresh() {
  store.load().catch(() => {})
}
function onSubmitForm(payload) {
  store.onSubmitForm(payload).catch(() => {})
}
function onToggle(item) {
  store.onToggle(item).catch(() => {})
}
function onConfirmDelete() {
  store.confirmDelete().catch(() => {})
}

// 自定义下拉选项（通用数据：{ label, value }）
const typeOptions = [
  { label: '全部', value: '' },
  { label: '寝室', value: 'dorm' },
  { label: '活动', value: 'activity' },
  { label: '寝室 + 活动', value: 'general' }
]
const signOptions = [
  { label: '全部', value: '' },
  { label: '签到成功', value: 'success' },
  { label: '签到失败', value: 'fail' },
  { label: '已跳过', value: 'skip' },
  { label: '从未签到', value: 'never' }
]
const enabledOptions = [
  { label: '全部', value: '' },
  { label: '启用', value: 'true' },
  { label: '禁用', value: 'false' }
]

// 签到类型映射：动态基于「已添加至定时任务且启用」的签到类型派生
// 两者都启用 → 寝室 + 活动；仅寝室 → 寝室签到；仅活动 → 活动签到；都未添加 → 未配置任务
function typeMeta(item) {
  const st = item.signTasks || []
  const dorm = st.some((t) => t.type === 'dorm' && t.enabled)
  const activity = st.some((t) => t.type === 'activity' && t.enabled)
  if (dorm && activity) return { label: '寝室 + 活动', cls: 'bg-ink/10 text-ink-soft' }
  if (dorm) return { label: '寝室签到', cls: 'bg-brand/10 text-brand' }
  if (activity) return { label: '活动签到', cls: 'bg-info/10 text-info' }
  return { label: '未配置任务', cls: 'bg-ink/5 text-ink-muted' }
}

// 上一次签到状态映射：label 用完整措辞（软标签内展示），tag 为标签底色
function signMeta(item) {
  const s = item.lastSignIn
  const status = (s && s.status) || 'never'
  if (status === 'success') return { label: '签到成功', cls: 'text-success', tag: 'bg-success/10 text-success', dot: 'bg-success' }
  if (status === 'fail') return { label: '签到失败', cls: 'text-danger', tag: 'bg-danger/10 text-danger', dot: 'bg-danger' }
  if (status === 'skip') return { label: '已跳过', cls: 'text-warning', tag: 'bg-warning/10 text-warning', dot: 'bg-warning' }
  return { label: '从未签到', cls: 'text-ink-muted', tag: 'bg-ink/5 text-ink-muted', dot: 'bg-ink/30' }
}

// 头像圆环颜色编码上次签到状态：绿=成功 / 红=失败 / 黄=跳过 / 灰=从未签到
function ringCls(item) {
  const status = (item.lastSignIn && item.lastSignIn.status) || 'never'
  return (
    { success: 'ring-success/60', fail: 'ring-danger/60', skip: 'ring-warning/60', never: 'ring-ink/15' }[status] ||
    'ring-ink/15'
  )
}

// 头像字符：优先姓名首字，否则取账号首字
function avatarChar(item) {
  const n = (item.profile && item.profile.name) || item.account || '?'
  return n.slice(0, 1)
}

// 院系行完整文案（truncate 后经 title 悬停查看全文）
function deptText(item) {
  const p = item.profile
  if (!p) return ''
  return [p.college, p.major, p.className].filter(Boolean).join(' · ')
}

// 该账号有自己推送目标的通道：绑了凭证，或单独指定了收件人（邮件）
function pushChannelsOf(item) {
  return activeChannels(item.pushCreds)
}

// 只指定了收件人、没绑凭证的通道用虚线标签区分「半落位」，避免看着像已绑定
function pushChipCls(item, ch) {
  const e = readCredEntry((item.pushCreds || {})[ch])
  return e.credId ? channelTone(ch) : 'border border-dashed border-ink/25 text-ink-soft'
}

function pushChipTitle(item, ch) {
  const e = readCredEntry((item.pushCreds || {})[ch])
  if (e.credId && e.to) return `已绑定凭证 · 收件人：${e.to}`
  if (e.credId) return '已绑定凭证'
  return `仅指定收件人：${e.to}（凭证跟随配置套）`
}

// 首次加载（store 内部负责拉取与状态管理；失败由全局 toast 提示）
refresh()
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
/* 预留滚动条宽度，避免出现纵向滚动条时内容区宽度抖动 */
.xb-scroll {
  scrollbar-gutter: stable;
}
</style>
