<template>
  <div class="flex flex-1 min-h-0 flex-col gap-6">
    <!-- 搜索卡片：平台账号筛选（带模糊搜索）居左，签到类型切换靠右 -->
    <div class="dash-card fade-up relative z-30 shrink-0 p-3 sm:p-4">
      <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
        <!-- 平台账号筛选：下拉框对账号名称模糊搜索，默认展示第一个账号 -->
        <div class="flex items-center gap-2">
          <span class="shrink-0 text-sm font-medium text-ink-soft">平台账号</span>
          <div class="w-44 sm:w-56">
            <BaseSelect
              v-model="selectedAccountId"
              :options="accountOptions"
              :searchable="true"
              :disabled="loadingAccounts"
              placeholder="选择账号"
              size="sm"
            />
          </div>
        </div>

        <!-- 签到类型切换：全部 / 寝室签到 / 活动签到，靠右对齐 -->
        <div class="ml-auto inline-flex items-center rounded-xl bg-cloud p-1">
          <button
            v-for="t in typeTabs"
            :key="t.value"
            type="button"
            class="rounded-lg px-3 py-1.5 text-sm font-medium transition"
            :class="typeFilter === t.value ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
            @click="store.setType(t.value)"
          >
            {{ t.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- 无账号空态：需先添加平台账号才有第三方签到数据 -->
    <div v-if="!loadingAccounts && accounts.length === 0" class="dash-card fade-up flex flex-1 flex-col items-center justify-center gap-2 text-ink-muted">
      <Icon name="user" :size="30" class="opacity-50" />
      <span>暂无已添加的平台账号，请先在「账号管理」中添加 B 平台账号。</span>
    </div>

    <template v-else>
      <!-- 统计卡片：仅统计当前所选账号 + 当前类型的签到数据 -->
      <div class="grid shrink-0 grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="签到总次数"
          :value="stats.signed"
          unit="次"
          icon="check-circle"
          tone="success"
          :loading="loadingRecords"
          :delay="1"
        />
        <StatCard
          label="漏签次数"
          :value="stats.unsigned"
          unit="次"
          icon="alert"
          tone="danger"
          :loading="loadingRecords"
          :delay="2"
        />
        <StatCard
          label="总签到任务"
          :value="stats.total"
          unit="项"
          icon="tasks"
          tone="brand"
          :loading="loadingRecords"
          :delay="3"
        />
      </div>

      <!-- 列表视图：卡片按内容自然展开，整页滚动；底部接入分页 -->
      <div v-if="viewMode === 'list'" class="dash-card fade-up flex min-h-[500px] flex-col rounded-2xl">
        <div class="flex shrink-0 items-center justify-between gap-3 border-b border-ink/10 px-4 py-2.5 sm:px-5">
          <h3 class="text-sm font-semibold text-ink">签到记录</h3>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-ink/10 px-3 text-sm font-medium text-ink-soft transition hover:bg-cloud disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="loadingRecords"
              @click="store.loadRecords"
            >
              <Icon name="refresh" :size="14" />刷新
            </button>
            <div class="inline-flex items-center rounded-xl bg-cloud p-1">
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition"
              :class="viewMode === 'list' ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
              @click="store.setView('list')"
            >
              <Icon name="records" :size="15" />列表
            </button>
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition"
              :class="viewMode === 'calendar' ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
              @click="store.setView('calendar')"
            >
              <Icon name="calendar" :size="15" />日历
            </button>
          </div>
          </div>
        </div>
        <div class="xb-scroll flex-1 min-h-0 overflow-auto px-4 sm:px-5">
          <table class="w-full table-fixed text-left text-sm">
            <colgroup>
              <col class="w-[26%]" />
              <col class="w-[14%]" />
              <col class="w-[16%]" />
              <col class="w-[12%]" />
              <col class="w-[16%]" />
              <col class="w-[16%]" />
            </colgroup>
            <thead class="sticky top-0 z-10">
              <tr class="border-b border-ink/10 text-ink-muted">
                <th class="bg-white px-3 py-2 font-medium">任务名称</th>
                <th class="bg-white px-3 py-2 font-medium">签到类型</th>
                <th class="bg-white px-3 py-2 font-medium">日期</th>
                <th class="bg-white px-3 py-2 font-medium">时间</th>
                <th class="bg-white px-3 py-2 font-medium">发起人</th>
                <th class="bg-white pl-5 pr-3 py-2.5 text-left font-medium">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loadingRecords" class="border-b border-ink/5">
                <td colspan="6" class="px-3 py-12 text-center text-ink-muted">加载中…</td>
              </tr>
              <tr v-else-if="listRows.length === 0" class="border-b border-ink/5">
                <td colspan="6" class="px-3">
                  <!-- 空态：固定高度占位避免高度塌陷，图标占位 + 文案提示 -->
                  <div class="flex min-h-[400px] flex-col items-center justify-center gap-3 py-6 text-ink-muted">
                    <Icon name="records" :size="36" class="opacity-40" />
                    <p class="text-sm font-medium text-ink-soft">暂无数据</p>
                    <p class="text-xs">当前筛选条件下还没有签到记录</p>
                  </div>
                </td>
              </tr>
              <tr
                v-for="row in pagedRows"
                v-else
                :key="row.id"
                class="border-b border-ink/5 transition last:border-0 hover:bg-cloud/40"
              >
                <td class="px-3 py-2.5 align-top">
                  <p class="truncate font-medium text-ink">{{ row.taskName }}</p>
                </td>
                <td class="px-3 py-2.5 align-top">
                  <span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap" :class="typeBadge(row.type).cls">
                    {{ typeBadge(row.type).label }}
                  </span>
                </td>
                <td class="px-3 py-2.5 align-top tabular-nums text-ink-soft">{{ row.date }}</td>
                <td class="px-3 py-2.5 align-top tabular-nums text-ink-soft">{{ row.time }}</td>
                <td class="px-3 py-2.5 align-top text-ink-soft">{{ row.initiator }}</td>
                <td class="px-3 py-2.5 align-top">
                  <span class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap" :class="statusBadge(row.status).cls">
                    <span class="h-1.5 w-1.5 rounded-full" :class="statusBadge(row.status).dot" />
                    {{ statusBadge(row.status).label }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 分页：有数据时展示，页码导航 + 每页条数控制 -->
        <div v-if="total > 0" class="shrink-0 border-t border-ink/10 px-4 py-2.5 sm:px-5">
          <BasePagination
            :page="page"
            :page-size="pageSize"
            :total="total"
            :page-size-options="[10, 20, 50]"
            @update:page="store.onPageChange"
            @update:page-size="store.onPageSizeChange"
          />
        </div>
      </div>

      <!-- 日历视图：卡片标题 + 居中月份标题行 + 自适应主体，与列表视图共用高度适配逻辑 -->
      <div v-else class="dash-card fade-up flex min-h-[500px] flex-col rounded-2xl">
        <!-- 卡片标题行：标题 + 视图切换 -->
        <div class="flex shrink-0 items-center justify-between gap-3 border-b border-ink/10 px-4 py-2.5 sm:px-5">
          <h3 class="text-sm font-semibold text-ink">签到日历</h3>
          <div class="inline-flex items-center rounded-xl bg-cloud p-1">
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition"
              :class="viewMode === 'list' ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
              @click="store.setView('list')"
            >
              <Icon name="records" :size="15" />列表
            </button>
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition"
              :class="viewMode === 'calendar' ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
              @click="store.setView('calendar')"
            >
              <Icon name="calendar" :size="15" />日历
            </button>
          </div>
        </div>

        <!-- 月份标题行：居中展示；左箭头+日期+右箭头保持间隔，右箭头旁以分隔线接「返回本月」 -->
        <div class="flex shrink-0 items-center justify-center gap-2 px-4 py-2 sm:px-5">
          <div class="flex items-center gap-3">
            <button type="button" class="grid h-8 w-8 place-items-center rounded-lg border border-ink/10 text-ink-muted transition hover:bg-cloud hover:text-ink" aria-label="上一月" @click="store.prevMonth">
              <Icon name="chevron-left" :size="16" />
            </button>
            <span class="text-base font-semibold text-ink tabular-nums">{{ monthLabel }}</span>
            <button type="button" class="grid h-8 w-8 place-items-center rounded-lg border border-ink/10 text-ink-muted transition hover:bg-cloud hover:text-ink" aria-label="下一月" @click="store.nextMonth">
              <Icon name="chevron-right" :size="16" />
            </button>
          </div>
          <span class="mx-1 h-5 w-px bg-ink/15" aria-hidden="true" />
          <button
            type="button"
            class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-ink/10 px-3 text-sm font-medium text-ink-soft transition hover:bg-cloud disabled:opacity-40 disabled:cursor-not-allowed"
            :disabled="isCurrentMonth"
            @click="store.backToCurrentMonth"
          >
            <Icon name="refresh" :size="14" />返回本月
          </button>
        </div>

        <!-- 日历主体：星期 + 日期网格 + 图例，随卡片高度自适应，内容超高时内部滚动 -->
        <div class="xb-scroll flex-1 min-h-0 overflow-auto px-4 py-3 sm:px-5">
          <div class="mb-1.5 grid grid-cols-7 gap-1.5 text-center text-xs font-medium text-ink-muted">
            <span v-for="w in WEEKDAYS" :key="w" class="py-1">{{ w }}</span>
          </div>

          <div v-if="loadingRecords" class="flex items-center justify-center py-10 text-sm text-ink-muted">加载中…</div>
          <div v-else class="grid grid-cols-7 gap-1.5">
            <template v-for="(cell, i) in calendarCells" :key="i">
              <div
                v-if="cell"
                class="flex min-h-[42px] flex-col items-center justify-center rounded-xl border text-sm transition"
                :class="cellClass(cell.state)"
              >
                <span class="font-semibold leading-none tabular-nums">{{ cell.day }}</span>
                <span v-if="cell.signed || cell.unsigned" class="mt-1 text-[10px] leading-none tabular-nums">
                  <template v-if="cell.signed">签{{ cell.signed }}</template>
                  <template v-if="cell.unsigned"> · 漏{{ cell.unsigned }}</template>
                </span>
              </div>
              <div v-else class="rounded-xl" />
            </template>
          </div>

          <div class="mt-4 flex items-center gap-4 border-t border-ink/5 pt-3 text-xs text-ink-muted">
            <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-success" />已签到</span>
            <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-danger" />未签到（漏签）</span>
            <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-ink/15" />无记录</span>
          </div>
        </div>
      </div>
    </template>
    <!-- 底部间距占位：真实在流子元素，盒高计入 scrollHeight，不受滚动容器末端 padding/margin 折叠影响；
         -mt-6 抵消根容器 gap-6，确保底部间距精确 24px、与其它页面一致 -->
    <div class="h-6 shrink-0 -mt-6" aria-hidden="true"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useSignRecordsStore } from '@/stores/signRecords'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import StatCard from '@/components/StatCard.vue'
import BasePagination from '@/components/BasePagination.vue'

// 领域状态下沉到 store：视图只做渲染与展示辅助，数据编排由 store 负责
const store = useSignRecordsStore()
const {
  accounts,
  selectedAccountId,
  loadingAccounts,
  loadingRecords,
  typeFilter,
  viewMode,
  calendarMonth,
  accountOptions,
  stats,
  listRows,
  total,
  totalPages,
  pagedRows,
  page,
  pageSize,
  byDate,
  isCurrentMonth
} = storeToRefs(store)

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']
const pad = (n) => String(n).padStart(2, '0')

const typeTabs = [
  { label: '全部', value: 'all' },
  { label: '寝室签到', value: 'dorm' },
  { label: '活动签到', value: 'activity' }
]

const monthLabel = computed(() => {
  const [y, m] = calendarMonth.value.split('-').map(Number)
  return `${y}年${m}月`
})

// 日历网格：按显示月份生成 6×7 单元格，依据 byDate 着色（漏签优先标红）
const calendarCells = computed(() => {
  const [y, m] = calendarMonth.value.split('-').map(Number)
  const first = new Date(y, m - 1, 1)
  const startWeekday = first.getDay()
  const daysInMonth = new Date(y, m, 0).getDate()
  const cells = []
  for (let i = 0; i < startWeekday; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) {
    const key = `${y}-${pad(m)}-${pad(d)}`
    const agg = byDate.value[key] || { signed: 0, unsigned: 0 }
    let state = 'none'
    if (agg.unsigned > 0) state = 'unsigned'
    else if (agg.signed > 0) state = 'signed'
    cells.push({ day: d, key, state, signed: agg.signed, unsigned: agg.unsigned })
  }
  while (cells.length % 7 !== 0) cells.push(null)
  return cells
})

function cellClass(state) {
  if (state === 'signed') return 'border-success/20 bg-success/10 text-success'
  if (state === 'unsigned') return 'border-danger/20 bg-danger/10 text-danger'
  return 'border-ink/5 text-ink-muted'
}

function typeBadge(t) {
  return t === 'activity'
    ? { label: '活动签到', cls: 'bg-info/10 text-info' }
    : { label: '寝室签到', cls: 'bg-brand/10 text-brand' }
}

function statusBadge(s) {
  return s === 'signed'
    ? { label: '已签到', cls: 'bg-success/10 text-success', dot: 'bg-success' }
    : { label: '未签到', cls: 'bg-danger/10 text-danger', dot: 'bg-danger' }
}

// 首次加载账号列表（默认选中第一个并触发记录拉取）
store.loadAccounts()
</script>

<style scoped>
/* 预留滚动条宽度，防止纵向滚动时表头与内容列错位 */
.xb-scroll {
  scrollbar-gutter: stable;
}
</style>
