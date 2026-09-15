<template>
  <div class="flex flex-col gap-6 lg:flex-1 lg:min-h-0">
    <!-- 筛选卡片：账号决定看谁的数据；类型与状态同行双胶囊，竖线分隔，维度不同不合并为同一控件 -->
    <div class="dash-card fade-up relative z-30 shrink-0 p-3 sm:p-4">
      <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
        <!-- 平台账号：决定数据归属，独立于筛选维度 -->
        <div class="flex items-center gap-2">
          <span class="shrink-0 text-sm font-medium text-ink-soft">平台账号</span>
          <!-- 宽度按「18 位身份证号 · 姓名」全量展示设计（约 250px），不再截断为省略号 -->
          <div class="w-64 sm:w-72">
            <BaseSelect
              :model-value="selectedAccountId"
              :options="accountOptions"
              :searchable="true"
              :disabled="loadingAccounts"
              placeholder="选择账号"
              size="sm"
              @update:model-value="store.selectAccount"
            />
          </div>
        </div>

        <!-- 类型 + 状态：双胶囊竖线分隔，label 嵌入为行内灰色提示 -->
        <div class="ml-auto flex flex-wrap items-center gap-2">
          <div class="inline-flex items-center gap-1 rounded-xl bg-cloud p-1">
            <span class="px-1.5 text-[11px] font-medium text-ink-muted">类型</span>
            <button
              v-for="t in typeTabs"
              :key="`ty-${t.value}`"
              type="button"
              class="whitespace-nowrap rounded-lg px-2.5 py-1.5 text-sm font-medium transition"
              :class="typeFilter === t.value ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
              @click="store.setType(t.value)"
            >
              {{ t.label }}
            </button>
          </div>

          <span class="h-5 w-px bg-ink/10" aria-hidden="true" />

          <div class="inline-flex items-center gap-1 rounded-xl bg-cloud p-1">
            <span class="px-1.5 text-[11px] font-medium text-ink-muted">状态</span>
            <button
              v-for="s in statusTabs"
              :key="`st-${s.value}`"
              type="button"
              :title="s.title"
              class="whitespace-nowrap rounded-lg px-2.5 py-1.5 text-sm font-medium transition"
              :class="statusFilter === s.value ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
              @click="store.setStatus(s.value)"
            >
              {{ s.label }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 无账号空态 -->
    <div v-if="!loadingAccounts && accounts.length === 0" class="dash-card fade-up flex flex-1 flex-col items-center justify-center gap-2 text-ink-muted">
      <Icon name="user" :size="30" class="opacity-50" />
      <span>暂无已添加的平台账号，请先在「账号管理」中添加 B 平台账号。</span>
    </div>

    <template v-else>
      <!-- 正在进行：当前账号此刻的任务（寝/活合并，含已签到但未结束的），置于统计与历史之前 -->
      <ActiveTasksCard @preview="openPreview" />

      <!-- 统计卡片：总任务 / 已签 / 未签 / 满勤率。满勤率用环形进度作视觉锚点，其余保持数字卡 -->
      <div class="grid shrink-0 grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="签到总任务" :value="stats.total" unit="项" icon="records" tone="brand" :loading="loadingRecords" :delay="1" count-up />
        <StatCard label="已签到" :value="stats.finished" unit="项" icon="check-circle" tone="success" :loading="loadingRecords" :delay="2" count-up />
        <StatCard label="未签到" :value="stats.unsigned" unit="项" icon="x-circle" tone="danger" :loading="loadingRecords" :delay="3" count-up />

        <div class="dash-card fade-up delay-4 flex min-h-[120px] items-center gap-4 p-5">
          <template v-if="loadingRecords">
            <div class="h-[76px] w-[76px] shrink-0 rounded-full border-[7px] border-ink/5 animate-pulse" />
            <div class="min-w-0 flex-1 space-y-2">
              <div class="h-4 w-16 rounded bg-ink/5 animate-pulse" />
              <div class="h-3 w-12 rounded bg-ink/5 animate-pulse" />
            </div>
          </template>
          <template v-else>
            <svg width="76" height="76" viewBox="0 0 76 76" class="shrink-0" aria-hidden="true">
              <circle cx="38" cy="38" r="30" fill="none" stroke="currentColor" stroke-width="7" class="text-ink/10" />
              <circle
                ref="rateArcRef"
                cx="38"
                cy="38"
                r="30"
                fill="none"
                stroke="currentColor"
                stroke-width="7"
                stroke-linecap="round"
                transform="rotate(-90 38 38)"
                :stroke-dasharray="RING_C"
                :stroke-dashoffset="RING_C"
                :class="rateToneClass"
              />
              <text
                x="38"
                y="38"
                text-anchor="middle"
                dominant-baseline="central"
                fill="currentColor"
                class="text-ink text-[17px] font-bold tabular-nums"
              >{{ stats.rate }}%</text>
            </svg>
            <div class="min-w-0 flex-1">
              <p class="text-sm font-medium text-ink-muted">满勤率</p>
              <p class="mt-1.5 truncate text-xs text-ink-muted">
                已签 <b class="tabular-nums text-success">{{ stats.finished }}</b>
                <span class="text-ink-muted">/ {{ stats.total }} 项</span>
              </p>
            </div>
          </template>
        </div>
      </div>

      <!-- 列表视图 -->
      <div v-if="viewMode === 'list'" class="dash-card fade-up flex min-h-[480px] flex-col rounded-2xl">
        <div class="flex shrink-0 items-center justify-between gap-3 border-b border-ink/10 px-4 py-2.5 sm:px-5">
          <h3 class="text-sm font-semibold text-ink">签到记录</h3>
          <div class="inline-flex items-center rounded-xl bg-cloud p-1">
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition"
              :class="viewMode === 'list' ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
              @click="store.setView('list')"
            >
              <Icon name="records" :size="14" />列表
            </button>
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition"
              :class="viewMode === 'calendar' ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
              @click="store.setView('calendar')"
            >
              <Icon name="calendar" :size="14" />日历
            </button>
          </div>
        </div>

        <!-- 按日筛选横幅 -->
        <div v-if="dayFilter" class="flex shrink-0 items-center gap-2 border-b border-ink/10 bg-brand/5 px-4 py-2 text-xs text-ink-soft sm:px-5">
          <Icon name="calendar" :size="13" class="text-brand" />
          <span>已筛选 <b class="tabular-nums text-ink">{{ dayFilter }}</b> 当天的任务（{{ total }} 项）</span>
          <button type="button" class="ml-auto rounded-md px-2 py-0.5 font-medium text-brand hover:bg-brand/10" @click="store.clearDayFilter">
            清除筛选
          </button>
        </div>

        <div
          class="xb-scroll overflow-auto px-2 transition-opacity sm:px-3 lg:flex-1 lg:min-h-0"
          :class="refreshingRecords && 'opacity-60 pointer-events-none'"
        >
          <!-- 加载中（仅首次进入，之后翻页/筛选原地静默换新） -->
          <div v-if="loadingRecords" class="flex items-center justify-center py-16 text-sm text-ink-muted">
            加载中…
          </div>

          <!-- 空态 -->
          <div v-else-if="pagedRows.length === 0" class="flex min-h-[400px] flex-col items-center justify-center gap-3 py-6 text-ink-muted">
            <Icon name="records" :size="36" class="opacity-40" />
            <p class="text-sm font-medium text-ink-soft">暂无数据</p>
            <p class="text-xs">
              {{ dayFilter ? '所选日期下没有签到任务' : '当前账号与筛选条件下还没有历史签到任务' }}
            </p>
          </div>

          <!-- 任务行（可展开） -->
          <ul ref="listRef" v-else class="divide-y divide-ink/5">
            <li v-for="row in pagedRows" :key="row.id" v-reveal data-task-row>
              <button
                type="button"
                class="flex w-full items-center gap-3 px-2 py-3 text-left transition hover:bg-cloud/40 sm:px-3"
                @click="store.toggleExpand(row)"
              >
                <!-- 状态色条：纵向扫列表时的第一视觉锚点 -->
                <span class="h-9 w-1 shrink-0 rounded-full" :class="row.finished ? 'bg-success' : 'bg-danger'" />

                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="truncate text-[15px] font-semibold text-ink">{{ row.taskName }}</span>
                    <span class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap" :class="taskTypeMeta(row.type).cls">
                      {{ taskTypeMeta(row.type).label }}
                    </span>
                    <span v-if="row.needPhoto" class="shrink-0 rounded-full bg-amber/10 px-2 py-0.5 text-xs font-medium text-amber whitespace-nowrap">需拍照</span>
                  </div>
                  <div class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
                    <span class="tabular-nums">{{ row.startDate }}<template v-if="row.endDate && row.endDate !== row.startDate"> ~ {{ row.endDate }}</template></span>
                    <span class="tabular-nums">{{ row.startTime }}<template v-if="row.endTime"> – {{ row.endTime }}</template></span>
                    <span class="truncate">发起人 {{ row.initiator }}</span>
                  </div>
                </div>

                <span class="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap" :class="statusBadge(row.finished).cls">
                  <span class="h-1.5 w-1.5 rounded-full" :class="statusBadge(row.finished).dot" />
                  {{ statusBadge(row.finished).label }}
                </span>

                <Icon
                  name="chevron-right"
                  :size="18"
                  class="shrink-0 text-ink-muted transition-transform"
                  :class="detailOf(row) && detailOf(row).open ? 'rotate-90' : ''"
                />
              </button>

              <!-- 展开详情：任务要素 + 地理围栏卡片 + 签到凭证 -->
              <Transition :css="false" @enter="onDetailEnter" @leave="onDetailLeave">
              <div v-if="detailOf(row) && detailOf(row).open" class="overflow-hidden border-t border-ink/5 bg-cloud/30 px-3 py-4 sm:px-5">
                <TaskDetailPanel :detail="detailOf(row)" :row="row" @preview="openPreview" />
              </div>
              </Transition>
            </li>
          </ul>
        </div>

        <!-- 分页 -->
        <div v-if="total > 0" class="shrink-0 border-t border-ink/10 px-4 py-2.5 sm:px-5">
          <BasePagination
            :page="page"
            :page-size="pageSize"
            :total="total"
            :page-size-options="[10, 20, 50]"
            @update:page="store.setPage"
            @update:page-size="store.setPageSize"
          />
        </div>
      </div>

      <!-- 日历视图 -->
      <div
        ref="calendarRef"
        v-else
        class="dash-card fade-up flex min-h-[600px] flex-1 flex-col rounded-2xl"
        @mouseover="onCellHover"
        @mouseout="onCellOut"
      >
        <!-- 卡片标题行：标题 + 视图切换（收进卡片内） -->
        <div class="flex shrink-0 items-center justify-between gap-3 border-b border-ink/10 px-4 py-2.5 sm:px-5">
          <h3 class="text-sm font-semibold text-ink">签到日历</h3>
          <div class="inline-flex items-center rounded-xl bg-cloud p-1">
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition"
              :class="viewMode === 'list' ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
              @click="store.setView('list')"
            >
              <Icon name="records" :size="14" />列表
            </button>
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition"
              :class="viewMode === 'calendar' ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
              @click="store.setView('calendar')"
            >
              <Icon name="calendar" :size="14" />日历
            </button>
          </div>
        </div>

        <!-- 月份导航 + 本月概览（签名元素：完成率进度条） -->
        <div class="flex shrink-0 flex-col gap-3 border-b border-ink/5 px-4 py-3 sm:px-5">
          <div class="flex items-center justify-between gap-3">
            <div class="flex items-center gap-3">
              <button type="button" class="grid h-8 w-8 place-items-center rounded-lg border border-ink/10 text-ink-muted transition hover:bg-cloud hover:text-ink" aria-label="上一月" @click="store.prevMonth">
                <Icon name="chevron-left" :size="16" />
              </button>
              <span ref="monthLabelRef" class="min-w-[96px] text-center text-base font-semibold tracking-tight text-ink tabular-nums">{{ calendarLabel }}</span>
              <button type="button" class="grid h-8 w-8 place-items-center rounded-lg border border-ink/10 text-ink-muted transition hover:bg-cloud hover:text-ink" aria-label="下一月" @click="store.nextMonth">
                <Icon name="chevron-right" :size="16" />
              </button>
            </div>
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-sm font-medium transition hover:bg-cloud disabled:cursor-not-allowed disabled:opacity-40"
                :class="isCurrentMonth ? 'border-ink/10 text-ink-soft' : 'border-brand/30 bg-brand/[0.06] text-brand'"
                :disabled="isCurrentMonth"
                @click="store.backToCurrentMonth"
              >
                <Icon name="refresh" :size="14" />今天
              </button>
              <button
                type="button"
                class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-ink/10 px-3 text-sm font-medium text-ink-soft transition hover:bg-cloud disabled:cursor-not-allowed disabled:opacity-40"
                :disabled="!bestDataMonth || (bestDataMonth.y === calendarYear && bestDataMonth.m === calendarMonth)"
                @click="store.jumpToBestMonth"
              >
                <Icon name="clock" :size="14" />最新数据
              </button>
            </div>
          </div>

          <!-- 本月概览：已签 / 漏签 / 完成率 -->
          <div class="flex items-center gap-3">
            <span class="whitespace-nowrap text-xs text-ink-muted">已签 <b class="text-sm font-semibold text-success tabular-nums">{{ monthSummary.signed }}</b></span>
            <span class="whitespace-nowrap text-xs text-ink-muted">漏签 <b class="text-sm font-semibold text-danger tabular-nums">{{ monthSummary.unsigned }}</b></span>
            <div class="relative h-1.5 flex-1 overflow-hidden rounded-full bg-ink/10">
              <div ref="progressRef" class="absolute inset-y-0 left-0 rounded-full bg-success" style="width: 0%" />
            </div>
            <span class="whitespace-nowrap text-xs font-medium text-ink-soft tabular-nums">{{ monthSummary.rate }}%</span>
          </div>
        </div>

        <!-- 星期表头（周日起）：周末列更淡，压低视觉噪音 -->
        <div class="grid shrink-0 grid-cols-7 gap-1.5 px-3 pb-1.5 pt-2.5 text-center text-[11px] font-medium tracking-wide text-ink-muted sm:px-4">
          <div v-for="(d, i) in weekHeads" :key="d" :class="i === 0 || i === 6 ? 'text-ink/35' : ''">{{ d }}</div>
        </div>

        <!-- 日期网格：flex-1 自适应铺满，6 行等分，内部不滚动。
             静默刷新期（切月取数）格子先以无记录灰渲染，数据到位即着色，不闪加载页 -->
        <div
          class="grid grid-cols-7 grid-rows-6 gap-1.5 px-3 pb-3 pt-1 transition-opacity sm:px-4 lg:flex-1 lg:min-h-0"
          :class="refreshingCalendar && 'opacity-60 pointer-events-none'"
        >
          <template v-if="(loadingRecords && !listLoaded) || (loadingCalendar && !calendarLoaded)">
            <div class="col-span-7 flex items-center justify-center text-sm text-ink-muted">加载中…</div>
          </template>
          <template v-else-if="stats.total === 0">
            <div class="col-span-7 flex flex-col items-center justify-center gap-2 text-ink-muted">
              <Icon name="calendar" :size="34" class="opacity-40" />
              <p class="text-sm">{{ statusFilter === 'all' ? `${calendarLabel} 暂无签到任务` : '当前筛选条件下没有签到任务' }}</p>
            </div>
          </template>
          <template v-else>
            <template v-for="(week, wi) in calendarWeeks" :key="wi">
              <button
                v-for="cell in week"
                :key="cell.date"
                type="button"
                data-day-cell
                class="group relative flex h-full flex-col items-center justify-center gap-1 rounded-xl border p-1.5 text-center transition-[background-color,border-color,color,box-shadow] duration-300"
                :class="[
                  cellClass(cell),
                  ringClass(cell),
                  cell.inMonth && cell.state !== 'none'
                    ? 'cursor-pointer hover:shadow-[0_2px_12px_-3px_rgba(15,23,42,0.15)]'
                    : 'cursor-default',
                ]"
                :disabled="!cell.inMonth || cell.state === 'none'"
                :title="cellTitle(cell)"
                @click="store.setDayFilter(cell.date)"
              >
                <span
                  class="text-sm font-semibold leading-none tabular-nums"
                  :class="cell.today ? 'text-brand' : (!cell.inMonth ? 'text-ink/30' : 'text-ink')"
                >{{ cell.day }}</span>
                <span
                  v-if="cell.inMonth && cell.state !== 'none'"
                  class="inline-flex items-center gap-1 rounded-full px-1.5 py-[3px] text-[10px] font-semibold leading-none tabular-nums"
                  :class="chipClass(cell.state)"
                >
                  <span class="h-1.5 w-1.5 rounded-full bg-current opacity-80" />
                  <template v-if="cell.signed > 0 && cell.unsigned > 0">签{{ cell.signed }}·漏{{ cell.unsigned }}</template>
                  <template v-else-if="cell.unsigned > 0">漏{{ cell.unsigned }}</template>
                  <template v-else>签{{ cell.signed }}</template>
                </span>
              </button>
            </template>
          </template>
        </div>

        <!-- 图例：始终渲染、固定高度，避免切换月份时布局跳动 -->
        <div class="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 border-t border-ink/5 px-4 py-2.5 text-xs text-ink-muted sm:px-5">
          <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-success" />已签到</span>
          <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-danger" />漏签</span>
          <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-ink/15" />无记录</span>
          <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-brand/20 ring-2 ring-brand/60 ring-offset-1" />今天</span>
        </div>

        <!-- 底部信息条：始终占位（固定最小高度），内容按需切换，杜绝切换月份时的高度跳动 -->
        <div class="flex shrink-0 min-h-[2.5rem] items-center justify-center px-4 pb-2 text-center text-xs text-ink-muted sm:px-5">
          <span v-if="dayFilter">
            已选中 <b class="tabular-nums text-ink-soft">{{ dayFilter }}</b>
            <button type="button" class="ml-1 rounded-md px-2 py-0.5 font-medium text-brand hover:bg-brand/10" @click="store.setView('list')">查看当天任务</button>
            <button type="button" class="ml-1 rounded-md px-2 py-0.5 font-medium text-ink-muted hover:bg-cloud" @click="store.clearDayFilter">清除筛选</button>
          </span>
          <template v-else-if="stats.total > 0 && !monthHasTask && !refreshingCalendar">
            <span>本月暂无签到记录</span>
            <button v-if="bestDataMonth" type="button" class="ml-1 rounded-md px-2 py-0.5 font-medium text-brand hover:bg-brand/10" @click="store.jumpToBestMonth">查看 {{ bestDataMonth.y }}年{{ bestDataMonth.m }}月</button>
          </template>
        </div>
      </div>
    </template>

    <!-- 底部间距占位：真实在流子元素，盒高计入 scrollHeight -->
    <div class="h-6 shrink-0 -mt-6" aria-hidden="true"></div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { gsap } from 'gsap'
// PhotoSwipe 与图库同款（样式已在 main.js 全局引入，此处不重复引）
import PhotoSwipeLightbox from 'photoswipe/lightbox'
import PhotoSwipe from 'photoswipe'
import { useSignRecordsStore } from '@/stores/signRecords'
import { taskTypeMeta } from '@/utils/accountType'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import StatCard from '@/components/StatCard.vue'
import BasePagination from '@/components/BasePagination.vue'
import ActiveTasksCard from '@/components/signrecords/ActiveTasksCard.vue'
import TaskDetailPanel from '@/components/signrecords/TaskDetailPanel.vue'
import { useCollapseTransition } from '@/composables/useCollapseTransition'

const store = useSignRecordsStore()
const {
  accounts,
  accountOptions,
  selectedAccountId,
  loadingAccounts,
  loadingRecords,
  loadingCalendar,
  refreshingRecords,
  refreshingCalendar,
  listLoaded,
  calendarLoaded,
  typeFilter,
  statusFilter,
  viewMode,
  stats,
  total,
  pagedRows,
  page,
  pageSize,
  calendarYear,
  calendarMonth,
  calendarLabel,
  calendarWeeks,
  dayFilter,
  monthHasTask,
  bestDataMonth,
  monthSummary,
  isCurrentMonth,
} = storeToRefs(store)

// 分行后横向不再拥挤，类型恢复完整文案，语义不必再靠 title 兜底
const typeTabs = [
  { label: '全部', value: 'all' },
  { label: '寝室签到', value: 'dorm' },
  { label: '活动签到', value: 'activity' },
]
const statusTabs = [
  { label: '全部', value: 'all', title: '全部状态' },
  { label: '已签到', value: 'signed', title: '已签到的任务' },
  { label: '未签到', value: 'unsigned', title: '未签到（漏签）的任务' },
  { label: '需拍照', value: 'needPhoto', title: '需要拍照的任务' },
]
// 周日起始，对齐旧版日历 UI
const weekHeads = ['日', '一', '二', '三', '四', '五', '六']

function statusBadge(finished) {
  return finished
    ? { label: '已签到', cls: 'bg-success/10 text-success', dot: 'bg-success' }
    : { label: '未签到', cls: 'bg-danger/10 text-danger', dot: 'bg-danger' }
}

// 模板里多次读同一任务的详情，收敛成一次查找，避免重复的 store.getDetail 调用
function detailOf(row) {
  return store.getDetail(row.id)
}

// 日历格底色：占位日期(上/下月)彻底弱化、当月无任务安静清晰、已签(绿)/漏签(红)区分明确。
// 今天即便当天没有任务也要一眼可辨，故单独给品牌色底 + 描边，且不受 inMonth 限制
// （今天可能落在当月的网格占位区，如 7 月网格会包含 8 月初）。
function cellClass(cell) {
  if (cell.today && cell.state === 'none') return 'border-brand/40 bg-brand/[0.06] text-brand'
  // 占位日期（上/下月）：透明无边框、文字极淡，明显区别于当月真实日期
  if (!cell.inMonth) return 'border-transparent bg-transparent text-ink/25'
  // 当月：柔和底色 + 同色描边，文字取满色保证可读
  if (cell.state === 'signed') return 'border-success/30 bg-success/10 text-success'
  if (cell.state === 'unsigned') return 'border-danger/30 bg-danger/10 text-danger'
  // 当月无任务：安静但在场（白底 + 极浅边框），与占位日期一眼可分
  return 'border-ink/[0.07] bg-white text-ink-soft'
}

// 环：选中态优先于今天，二者只取其一，避免两个 ring 工具类在 CSS 中互相覆盖
function ringClass(cell) {
  if (cell.date === dayFilter) return 'ring-2 ring-brand'
  if (cell.today) return 'ring-2 ring-brand/60'
  return ''
}

// 日历格状态小标签配色，与底色呼应（实心点 + 粗体数字，小尺寸下也清晰）
function chipClass(state) {
  if (state === 'signed') return 'bg-success/25 text-success'
  return 'bg-danger/25 text-danger'
}

// 悬浮提示：同时给出当天的已签 / 漏签任务条数；今天额外标注
function cellTitle(cell) {
  const suffix = cell.today ? '（今天）' : ''
  if (cell.state === 'none') return `${cell.date}${suffix}`
  const parts = []
  if (cell.signed) parts.push(`已签 ${cell.signed}`)
  if (cell.unsigned) parts.push(`漏签 ${cell.unsigned}`)
  return `${cell.date}${suffix} · ${parts.join(' · ')}`
}

// ---- 日历动效（GSAP）----
// 切月时格子错落淡入、完成率进度条补间、格子悬浮微缩放；统一尊重系统「减少动态效果」偏好
const calendarRef = ref(null)
const monthLabelRef = ref(null)
const progressRef = ref(null)
const reduceMotion = ref(false)
let mm = null

// ---- 列表与展开详情动效 ----
const listRef = ref(null)
// 行错落入场：翻页 / 切换筛选 / 回到列表时重放，展开详情不触发（避免整列表闪烁）
function staggerRows() {
  const root = listRef.value
  if (!root || reduceMotion.value) return
  const rows = root.querySelectorAll('[data-task-row]')
  if (!rows.length) return
  gsap.fromTo(
    rows,
    { autoAlpha: 0, y: 10 },
    {
      autoAlpha: 1,
      y: 0,
      duration: 0.36,
      stagger: 0.035,
      ease: 'power2.out',
      overwrite: true,
      clearProps: 'opacity,transform',
    }
  )
}

// 详情高度补间：纵向 padding 必须一起归零，否则收起后会残留一段空白。
// 逻辑抽到组合式，历史列表与「正在进行」卡片详情共用。
const { onEnter: onDetailEnter, onLeave: onDetailLeave } = useCollapseTransition(
  () => reduceMotion.value,
  { pad: 16 } // 与模板 py-4 对齐
)

watch([page, statusFilter, typeFilter, dayFilter, viewMode], async () => {
  if (viewMode.value !== 'list') return
  await nextTick()
  staggerRows()
})
// 首次数据到位时补一次入场（账号异步加载，列表晚于组件挂载）
watch(loadingRecords, async (v) => {
  if (v || viewMode.value !== 'list') return
  await nextTick()
  staggerRows()
})

// 进度条宽度交给 GSAP 驱动：模板里初始 0%，避免与 Vue 的内联样式互相覆盖
function animateProgress(rate) {
  if (!progressRef.value) return
  const w = Math.min(100, Math.max(0, Number(rate) || 0))
  gsap.to(progressRef.value, {
    width: `${w}%`,
    duration: reduceMotion.value ? 0 : 0.85,
    ease: 'power3.out',
    overwrite: true,
  })
}

// dir：1=下一月，-1=上一月，0=进入日历视图（不做方向位移）
async function animateCalendar(dir = 0) {
  await nextTick()
  const root = calendarRef.value
  if (!root) return
  const cells = root.querySelectorAll('[data-day-cell]')
  if (reduceMotion.value) {
    if (cells.length) gsap.set(cells, { autoAlpha: 1, y: 0, scale: 1 })
    animateProgress(monthSummary.value?.rate)
    return
  }
  if (cells.length) {
    gsap.fromTo(
      cells,
      { autoAlpha: 0, y: 12 * (dir || 1), scale: 0.96 },
      {
        autoAlpha: 1,
        y: 0,
        scale: 1,
        duration: 0.42,
        ease: 'power2.out',
        stagger: { each: 0.011, from: 'start' },
        overwrite: true,
      }
    )
  }
  if (dir && monthLabelRef.value) {
    gsap.fromTo(
      monthLabelRef.value,
      { autoAlpha: 0, x: 14 * dir },
      { autoAlpha: 1, x: 0, duration: 0.36, ease: 'power2.out', overwrite: true }
    )
  }
  animateProgress(monthSummary.value?.rate)
}

// 悬浮微交互用事件委托挂在日历根节点，避免给 42 个格子各绑一对监听
function hoveredCell(e) {
  const el = e.target instanceof Element ? e.target : null
  return el ? el.closest('[data-day-cell]') : null
}

function onCellHover(e) {
  const cell = hoveredCell(e)
  if (!cell || cell.disabled || reduceMotion.value) return
  gsap.to(cell, { scale: 1.05, duration: 0.22, ease: 'power2.out', overwrite: 'auto' })
}

function onCellOut(e) {
  const cell = hoveredCell(e)
  if (!cell || reduceMotion.value) return
  // 指针仍在同格的子元素之间移动时忽略，否则会来回抖动
  if (e.relatedTarget instanceof Node && cell.contains(e.relatedTarget)) return
  gsap.to(cell, { scale: 1, duration: 0.22, ease: 'power2.out', overwrite: 'auto' })
}

onMounted(() => {
  mm = gsap.matchMedia()
  mm.add('(prefers-reduced-motion: reduce)', () => {
    reduceMotion.value = true
    return () => {
      reduceMotion.value = false
    }
  })
})

// 账号是异步加载的，日历卡片要等数据到位才挂载；ref 由 null 变为元素时补一次入场动画
// （同时覆盖「首次进入」与「列表→日历」切换，避免与月份监听重复触发）
watch(calendarRef, (el) => {
  if (el) animateCalendar(0)
})

watch([calendarYear, calendarMonth], ([ny, nm], [oy, om]) => {
  if (viewMode.value !== 'calendar') return
  animateCalendar(ny > oy || (ny === oy && nm > om) ? 1 : -1)
})

watch(
  () => monthSummary.value?.rate,
  (r) => {
    if (viewMode.value === 'calendar') animateProgress(r)
  }
)

// ---- 满勤率环（统计卡签名元素）----
// 周长固定，进度只靠 stroke-dashoffset 补间；配色按完成率分档，让颜色本身传递状态
const RING_C = 2 * Math.PI * 30
const rateArcRef = ref(null)
const rateToneClass = computed(() => {
  const r = stats.value?.rate ?? 0
  if (r >= 100) return 'text-success'
  if (r >= 80) return 'text-brand'
  return 'text-amber'
})
function animateRateRing(rate) {
  if (!rateArcRef.value) return
  const r = Math.min(100, Math.max(0, Number(rate) || 0))
  gsap.to(rateArcRef.value, {
    strokeDashoffset: RING_C * (1 - r / 100),
    duration: reduceMotion.value ? 0 : 0.9,
    ease: 'power3.out',
    overwrite: true,
  })
}
// 环形在 loading 结束后才挂载，故连同 loadingRecords 一起监听，等 DOM 就绪再补间
watch(
  [() => stats.value?.rate, loadingRecords],
  async ([r]) => {
    await nextTick()
    animateRateRing(r)
  },
  { immediate: true }
)

onUnmounted(() => {
  mm?.revert()
  lightbox?.destroy()
  if (calendarRef.value) gsap.killTweensOf(calendarRef.value.querySelectorAll('[data-day-cell]'))
  gsap.killTweensOf([monthLabelRef.value, progressRef.value, rateArcRef.value].filter(Boolean))
})

// ---- 签到照片全屏（复用图库同款 PhotoSwipe）----
// v5 必须显式给出 width/height：缺失时它无从判断原始比例，会按视口铺满拉伸，滚轮缩放也失效
const sizeCache = new Map()
function probeSize(src) {
  if (!sizeCache.has(src)) {
    sizeCache.set(
      src,
      new Promise((resolve) => {
        const im = new Image()
        im.onload = () => resolve({ width: im.naturalWidth || 0, height: im.naturalHeight || 0 })
        im.onerror = () => resolve({ width: 0, height: 0 })
        im.src = src
      })
    )
  }
  return sizeCache.get(src)
}

let lightbox = null
async function openPreview(log) {
  if (!log || !log.imageUrl) return
  // 每次打开都新建实例，先销毁旧的，避免残留 DOM 与事件监听
  lightbox?.destroy()
  const { width, height } = await probeSize(log.imageUrl)
  // 单图时 PhotoSwipe 自动隐藏左右箭头与计数器
  lightbox = new PhotoSwipeLightbox({
    dataSource: [width && height ? { src: log.imageUrl, width, height } : { src: log.imageUrl }],
    index: 0,
    showHideAnimationType: 'fade',
    wheelToZoom: true,
    pswpModule: PhotoSwipe,
  })
  lightbox.init()
  lightbox.loadAndOpen(0)
}

store.loadAccounts()
</script>

<style scoped>
.xb-scroll {
  scrollbar-gutter: stable;
}
</style>
