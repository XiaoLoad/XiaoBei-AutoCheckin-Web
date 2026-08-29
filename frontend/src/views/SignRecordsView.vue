<template>
  <div class="flex flex-1 min-h-0 flex-col gap-6">
    <!-- 筛选卡片：平台账号（带搜索）居左；右侧为类型切换 -->
    <div class="dash-card fade-up relative z-30 shrink-0 p-3 sm:p-4">
      <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
        <div class="flex items-center gap-2">
          <span class="shrink-0 text-sm font-medium text-ink-soft">平台账号</span>
          <div class="w-44 sm:w-56">
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

        <div class="ml-auto inline-flex items-center gap-2">
          <!-- 签到类型切换 -->
          <div class="inline-flex items-center rounded-xl bg-cloud p-1">
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
    </div>

    <!-- 无账号空态 -->
    <div v-if="!loadingAccounts && accounts.length === 0" class="dash-card fade-up flex flex-1 flex-col items-center justify-center gap-2 text-ink-muted">
      <Icon name="user" :size="30" class="opacity-50" />
      <span>暂无已添加的平台账号，请先在「账号管理」中添加 B 平台账号。</span>
    </div>

    <template v-else>
      <!-- 统计卡片：当前账号 + 类型的全量任务聚合 -->
      <div class="grid shrink-0 grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="历史任务" :value="stats.total" unit="项" icon="records" tone="brand" :loading="loadingRecords" :delay="1" />
        <StatCard label="已完成" :value="stats.finished" unit="项" icon="check-circle" tone="success" :loading="loadingRecords" :delay="2" />
        <StatCard label="需拍照" :value="stats.needPhoto" unit="项" icon="image" tone="amber" :loading="loadingRecords" :delay="3" />
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

        <div class="xb-scroll flex-1 min-h-0 overflow-auto px-2 sm:px-3">
          <!-- 加载中 -->
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
          <ul v-else class="divide-y divide-ink/5">
            <li v-for="row in pagedRows" :key="row.id">
              <button
                type="button"
                class="flex w-full items-center justify-between gap-3 px-2 py-3 text-left transition hover:bg-cloud/40 sm:px-3"
                @click="store.toggleExpand(row)"
              >
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <span class="truncate font-medium text-ink">{{ row.taskName }}</span>
                    <span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap" :class="typeBadge(row.type).cls">
                      {{ typeBadge(row.type).label }}
                    </span>
                  </div>
                  <div class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
                    <span class="tabular-nums">{{ row.startDate }}<template v-if="row.endDate && row.endDate !== row.startDate"> ~ {{ row.endDate }}</template></span>
                    <span class="tabular-nums">{{ row.startTime }}<template v-if="row.endTime"> – {{ row.endTime }}</template></span>
                    <span>发起人 {{ row.initiator }}</span>
                    <span v-if="row.needPhoto" class="inline-flex items-center rounded-full bg-amber/10 px-2 py-0.5 text-xs font-medium text-amber whitespace-nowrap">需拍照</span>
                    <span class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap" :class="statusBadge(row.finished).cls">
                      <span class="h-1.5 w-1.5 rounded-full" :class="statusBadge(row.finished).dot" />
                      {{ statusBadge(row.finished).label }}
                    </span>
                  </div>
                </div>
                <Icon
                  name="chevron-right"
                  :size="18"
                  class="shrink-0 text-ink-muted transition-transform"
                  :class="store.getDetail(row.id) && store.getDetail(row.id).open ? 'rotate-90' : ''"
                />
              </button>

              <!-- 展开详情：地理围栏读取单元 + 签到记录子行 -->
              <div v-if="store.getDetail(row.id) && store.getDetail(row.id).open" class="border-t border-ink/5 bg-cloud/30 px-3 py-4 sm:px-5">
                <div v-if="store.getDetail(row.id).loading" class="flex items-center justify-center py-8 text-sm text-ink-muted">
                  加载详情中…
                </div>
                <div v-else-if="store.getDetail(row.id).error" class="py-2 text-sm text-danger">
                  {{ store.getDetail(row.id).error }}
                </div>
                <div v-else class="space-y-4">
                  <!-- 地理围栏读取单元（签名元素：细环 + 中心点） -->
                  <div class="flex gap-3 rounded-xl border border-amber/20 bg-amber/5 p-3">
                    <svg width="44" height="44" viewBox="0 0 44 44" class="shrink-0" aria-hidden="true">
                      <circle cx="22" cy="22" r="17" fill="none" stroke="#F2A65A" stroke-width="1.5" opacity="0.45" />
                      <circle cx="22" cy="22" r="10" fill="none" stroke="#F2A65A" stroke-width="1.5" />
                      <circle cx="22" cy="22" r="2.5" fill="#F2A65A" />
                    </svg>
                    <div class="min-w-0 flex-1 text-xs">
                      <p class="mb-1 text-[11px] font-medium uppercase tracking-wide text-amber">地理围栏</p>
                      <template v-if="store.getDetail(row.id).geoFence.length">
                        <div v-for="(g, gi) in store.getDetail(row.id).geoFence" :key="gi" class="space-y-0.5 text-ink-soft">
                          <p><span class="text-ink-muted">别名</span> <b class="text-ink">{{ g.alias || '—' }}</b> <span class="text-ink-muted">· 半径</span> {{ g.radius || '—' }}m</p>
                          <p class="tabular-nums"><span class="text-ink-muted">中心坐标</span> {{ g.latitude || '—' }}, {{ g.longitude || '—' }}</p>
                          <p class="truncate"><span class="text-ink-muted">地址</span> {{ g.location || '—' }}</p>
                        </div>
                      </template>
                      <p v-else class="text-ink-muted">该任务无地理围栏信息</p>
                    </div>
                  </div>

                  <!-- 签到记录子行 -->
                  <div class="space-y-2">
                    <p class="text-[11px] font-medium uppercase tracking-wide text-ink-muted">
                      签到记录（{{ store.getDetail(row.id).logs.length }}）
                    </p>
                    <div
                      v-for="log in store.getDetail(row.id).logs"
                      :key="log.id"
                      class="flex items-center gap-3 rounded-lg border border-ink/5 bg-white px-3 py-2"
                    >
                      <div class="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand/10 text-sm font-medium text-brand">
                        {{ (log.studentName || '?').charAt(0) }}
                      </div>
                      <div class="min-w-0 flex-1">
                        <p class="truncate text-sm text-ink">
                          {{ log.studentName || '—' }}
                          <span class="text-ink-muted">· {{ log.studentNumber || '—' }}</span>
                        </p>
                        <p class="truncate text-xs text-ink-muted tabular-nums">
                          {{ log.className || '—' }} · {{ log.time || '—' }} · 定位 {{ log.location || '—' }} · {{ log.remark || '无备注' }}
                        </p>
                      </div>
                      <img
                        v-if="log.imageUrl && !brokenImgs.has(row.id + '-' + log.id)"
                        :src="log.imageUrl"
                        class="h-12 w-12 shrink-0 rounded-lg border border-ink/5 object-cover"
                        loading="lazy"
                        alt="签到图片"
                        @error="onImgError(row.id, log.id)"
                      />
                      <span v-else class="shrink-0 text-[11px] text-ink-muted">无图</span>
                    </div>
                    <p v-if="store.getDetail(row.id).logs.length === 0" class="text-xs text-ink-muted">暂无签到记录</p>
                  </div>
                </div>
              </div>
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
      <div v-else class="dash-card fade-up flex min-h-[480px] flex-1 flex-col rounded-2xl">
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
              <span class="min-w-[88px] text-center text-base font-semibold text-ink tabular-nums">{{ calendarLabel }}</span>
              <button type="button" class="grid h-8 w-8 place-items-center rounded-lg border border-ink/10 text-ink-muted transition hover:bg-cloud hover:text-ink" aria-label="下一月" @click="store.nextMonth">
                <Icon name="chevron-right" :size="16" />
              </button>
            </div>
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-ink/10 px-3 text-sm font-medium text-ink-soft transition hover:bg-cloud disabled:cursor-not-allowed disabled:opacity-40"
                :disabled="isCurrentMonth"
                @click="store.backToCurrentMonth"
              >
                <Icon name="refresh" :size="14" />本月
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
              <div class="absolute inset-y-0 left-0 rounded-full bg-success transition-all duration-500" :style="{ width: monthSummary.rate + '%' }" />
            </div>
            <span class="whitespace-nowrap text-xs font-medium text-ink-soft tabular-nums">{{ monthSummary.rate }}%</span>
            <span v-if="loadingLogs" class="inline-flex items-center gap-1 whitespace-nowrap text-xs text-brand">
              <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-brand" />聚合中
            </span>
          </div>
        </div>

        <!-- 星期表头（周日起，对齐旧版 UI） -->
        <div class="grid shrink-0 grid-cols-7 gap-1.5 px-3 pb-1 pt-2 text-center text-xs font-medium text-ink-muted sm:px-4">
          <div v-for="d in weekHeads" :key="d">{{ d }}</div>
        </div>

        <!-- 日期网格：flex-1 自适应铺满，6 行等分，内部不滚动 -->
        <div class="grid min-h-0 flex-1 grid-cols-7 grid-rows-6 gap-1.5 px-3 pb-3 pt-1 sm:px-4">
          <template v-if="loadingRecords">
            <div class="col-span-7 flex items-center justify-center text-sm text-ink-muted">加载中…</div>
          </template>
          <template v-else-if="tasks.length === 0">
            <div class="col-span-7 flex flex-col items-center justify-center gap-2 text-ink-muted">
              <Icon name="calendar" :size="34" class="opacity-40" />
              <p class="text-sm">{{ calendarLabel }} 暂无签到任务</p>
            </div>
          </template>
          <template v-else>
            <template v-for="(week, wi) in calendarWeeks" :key="wi">
              <button
                v-for="cell in week"
                :key="cell.date"
                type="button"
                class="group relative flex h-full flex-col justify-between overflow-hidden rounded-xl border px-1.5 py-1 text-left transition"
                :class="[
                  cellClass(cell.state),
                  cell.inMonth ? '' : 'opacity-35',
                  cell.state === 'none' ? 'cursor-default' : 'cursor-pointer hover:brightness-[0.97]',
                  cell.date === dayFilter ? 'ring-2 ring-brand' : '',
                ]"
                :disabled="cell.state === 'none'"
                :title="cellTitle(cell)"
                @click="store.setDayFilter(cell.date)"
              >
                <span class="text-xs font-semibold leading-none tabular-nums" :class="cell.inMonth ? '' : 'text-ink-muted'">{{ cell.day }}</span>
                <span v-if="cell.state !== 'none'" class="self-start rounded-md px-1 py-0.5 text-[10px] font-medium leading-none tabular-nums" :class="chipClass(cell.state)">
                  <template v-if="cell.state === 'pending'">有任务</template>
                  <template v-else-if="cell.state === 'signed'">签{{ cell.signed }}</template>
                  <template v-else>漏{{ cell.unsigned }}</template>
                </span>
              </button>
            </template>
          </template>
        </div>

        <!-- 跨月提示：当前月无数据但有数据月份 -->
        <div v-if="tasks.length > 0 && !monthHasTask" class="flex shrink-0 items-center justify-center gap-2 border-t border-ink/5 px-4 py-2 text-xs text-ink-muted">
          <span>本月暂无签到记录</span>
          <button v-if="bestDataMonth" type="button" class="rounded-md px-2 py-0.5 font-medium text-brand hover:bg-brand/10" @click="store.jumpToBestMonth">
            查看 {{ bestDataMonth.y }}年{{ bestDataMonth.m }}月
          </button>
        </div>

        <!-- 图例 -->
        <div class="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 border-t border-ink/5 px-4 py-2.5 text-xs text-ink-muted sm:px-5">
          <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-success" />已签到</span>
          <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-danger" />漏签</span>
          <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-brand" />待聚合</span>
          <span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-ink/15" />无记录</span>
        </div>

        <p v-if="dayFilter" class="shrink-0 px-4 pb-2 text-center text-xs text-ink-muted sm:px-5">
          已选中 <b class="tabular-nums text-ink-soft">{{ dayFilter }}</b>，点击上方「列表」可查看当天任务明细
        </p>
      </div>
    </template>

    <!-- 底部间距占位：真实在流子元素，盒高计入 scrollHeight -->
    <div class="h-6 shrink-0 -mt-6" aria-hidden="true"></div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useSignRecordsStore } from '@/stores/signRecords'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import StatCard from '@/components/StatCard.vue'
import BasePagination from '@/components/BasePagination.vue'

const store = useSignRecordsStore()
const {
  accounts,
  accountOptions,
  selectedAccountId,
  loadingAccounts,
  loadingRecords,
  loadingLogs,
  logsReady,
  tasks,
  typeFilter,
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

const typeTabs = [
  { label: '全部', value: 'all' },
  { label: '寝室签到', value: 'dorm' },
  { label: '活动签到', value: 'activity' },
]
// 周日起始，对齐旧版日历 UI
const weekHeads = ['日', '一', '二', '三', '四', '五', '六']

function typeBadge(t) {
  return t === 'activity'
    ? { label: '活动签到', cls: 'bg-info/10 text-info' }
    : { label: '寝室签到', cls: 'bg-brand/10 text-brand' }
}

function statusBadge(finished) {
  return finished
    ? { label: '已完成', cls: 'bg-success/10 text-success', dot: 'bg-success' }
    : { label: '进行中', cls: 'bg-ink/10 text-ink-muted', dot: 'bg-ink/30' }
}

// 日历格底色：已签(绿) / 漏签(红) / 待聚合(品牌蓝) / 无记录(灰)
function cellClass(state) {
  if (state === 'signed') return 'border-success/30 bg-success/10 text-success'
  if (state === 'unsigned') return 'border-danger/30 bg-danger/10 text-danger'
  if (state === 'pending') return 'border-brand/25 bg-brand/5 text-brand'
  return 'border-ink/5 bg-white text-ink-muted'
}

// 日历格状态小标签配色，与底色呼应
function chipClass(state) {
  if (state === 'signed') return 'bg-success/15 text-success'
  if (state === 'unsigned') return 'bg-danger/15 text-danger'
  return 'bg-brand/10 text-brand'
}

// 悬浮提示：区分已签 / 漏签 / 待聚合 的语义文案
function cellTitle(cell) {
  if (cell.state === 'none') return cell.date
  const map = {
    signed: `已签 ${cell.signed}`,
    unsigned: `漏签 ${cell.unsigned}`,
    pending: '有任务（聚合中）',
  }
  return `${cell.date} · ${map[cell.state] || ''}`
}

// 直连 B 平台图片，加载失败的记录（taskId-logId 维度）回退为「无图」
const brokenImgs = ref(new Set())
function onImgError(taskId, logId) {
  brokenImgs.value = new Set(brokenImgs.value).add(`${taskId}-${logId}`)
}

store.loadAccounts()
</script>

<style scoped>
.xb-scroll {
  scrollbar-gutter: stable;
}
</style>
