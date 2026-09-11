<template>
  <div class="flex flex-col gap-4 sm:gap-5 lg:flex-1 lg:min-h-0">
    <!-- 页首导语：仅此一行解释性文案，左侧品牌色短竖线作为页面起的"引子" -->
    <div class="flex shrink-0 items-start gap-2.5 text-[13px] leading-relaxed text-ink-muted">
      <span class="mt-[7px] h-3 w-[3px] shrink-0 rounded-full bg-brand/60" aria-hidden="true" />
      <p>左侧账号树定位「哪个用户的哪个 B 平台账号」，右侧核对该账号在 B 平台的历史签到记录，行可展开看围栏与凭证。</p>
    </div>

    <!-- 两栏容器在有界高度里铺满剩余视口：两侧同时被拉伸到同一高度，底部自然对齐。
         左树不再单独限高——原先只有它带 lg:max-h-[calc(100vh-13rem)]、右卡没有，
         一侧有上限一侧没有正是"左右底部不齐"的根因；现在右卡改为列表内部滚动 -->
    <div class="flex flex-col gap-4 lg:min-h-0 lg:flex-1 lg:flex-row">
      <!-- ============ 左：账号树（与右卡同材质，两栏不再两种卡片） ============ -->
      <AccountTree class="dash-card max-h-[560px] shrink-0 lg:max-h-none lg:w-[336px]" />

      <!-- ============ 右：签到记录区 ============ -->
      <div class="dash-card flex min-h-[520px] flex-col overflow-hidden lg:min-h-0 lg:min-w-0 lg:flex-1">
        <!-- 上下文条：所选账号身份 + 审计读数（全历史口径，跟随类型/状态筛选） -->
        <div class="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-2.5 border-b border-ink/5 px-4 py-3 sm:px-5">
          <template v-if="selectedAccount">
            <div class="flex min-w-0 items-baseline gap-2">
              <h3 class="truncate text-[15px] font-semibold tabular-nums text-ink">{{ selectedAccount.account }}</h3>
              <span v-if="selectedAccount.profile && selectedAccount.profile.name" class="truncate text-[13px] text-ink-soft">
                {{ selectedAccount.profile.name }}
              </span>
            </div>
            <span class="shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-medium" :class="typeBadge(selectedAccount.type).cls">
              {{ typeBadge(selectedAccount.type).label }}
            </span>
            <!-- 验证状态是「状态」不是「标签」：圆点 + 文字，不再占用胶囊 -->
            <span
              class="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap text-xs font-medium"
              :class="selectedAccount.verifyStatus === 'ok' ? 'text-success' : 'text-danger'"
            >
              <span class="h-1.5 w-1.5 rounded-full" :class="selectedAccount.verifyStatus === 'ok' ? 'bg-success' : 'bg-danger'" />
              {{ selectedAccount.verifyStatus === 'ok' ? '验证正常' : '凭证异常' }}
            </span>
            <span class="hidden items-center gap-1 text-[11.5px] text-ink-muted sm:inline-flex">
              所属用户 <b class="font-medium text-ink-soft">{{ selectedAccount.owner }}</b>
            </span>
          </template>
          <h3 v-else class="text-[15px] font-semibold text-ink">签到记录</h3>

          <!-- 审计读数簇：四个数同处一块，靠细分隔线分区，满勤率是唯一的强调数字 -->
          <div
            v-if="selectedAccount"
            class="ml-auto flex shrink-0 items-stretch overflow-hidden rounded-xl bg-cloud/70 ring-1 ring-inset ring-ink/5"
          >
            <div class="px-2.5 py-1 text-center sm:px-3">
              <div class="text-[10px] leading-tight text-ink-muted sm:text-[10.5px]">总任务</div>
              <div class="mt-1 text-[15px] font-semibold leading-none tabular-nums text-ink">{{ overview.total }}</div>
            </div>
            <span class="my-1.5 w-px bg-ink/10" aria-hidden="true" />
            <div class="px-2.5 py-1 text-center sm:px-3">
              <div class="text-[10px] leading-tight text-ink-muted sm:text-[10.5px]">已签</div>
              <div class="mt-1 text-[15px] font-semibold leading-none tabular-nums text-success">{{ overview.finished }}</div>
            </div>
            <span class="my-1.5 w-px bg-ink/10" aria-hidden="true" />
            <div class="px-2.5 py-1 text-center sm:px-3">
              <div class="text-[10px] leading-tight text-ink-muted sm:text-[10.5px]">未签</div>
              <div class="mt-1 text-[15px] font-semibold leading-none tabular-nums text-danger">{{ overview.unsigned }}</div>
            </div>
            <span class="my-1.5 w-px bg-ink/10" aria-hidden="true" />
            <div class="bg-white/50 px-2.5 py-1 text-center sm:px-3">
              <div class="text-[10px] leading-tight text-ink-muted sm:text-[10.5px]">满勤率</div>
              <div class="mt-1 flex items-baseline justify-center gap-0.5">
                <span class="text-[15px] font-bold leading-none tabular-nums text-brand">{{ overview.rate }}</span>
                <span class="text-[10px] text-ink-muted">%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 筛选控制台：类型 / 状态 / 日期三组同处一轨，靠细分隔线分区。
             日期改用自定义区间选择器——单个触发器约 120px，取代原先两个 116px 原生输入框，
             三组因此能落在同一行（此前换行正是日期组被两个输入框撑爆宽度所致） -->
        <div class="flex shrink-0 flex-wrap items-center gap-2 border-b border-ink/5 bg-cloud/40 px-4 py-2.5 sm:px-5">
          <div class="flex flex-wrap items-center gap-x-1.5 gap-y-1 rounded-xl bg-ink/5 p-1">
            <div class="inline-flex items-center gap-1" role="group" aria-label="任务类型筛选">
              <span class="px-1.5 text-[10.5px] font-medium text-ink-muted">类型</span>
              <button
                v-for="t in typeTabs"
                :key="`ty-${t.value}`"
                type="button"
                :aria-pressed="typeFilter === t.value"
                class="whitespace-nowrap rounded-lg px-2 py-1.5 text-[13px] font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
                :class="typeFilter === t.value ? 'bg-white text-brand shadow-sm ring-1 ring-ink/5' : 'text-ink-muted hover:text-ink-soft'"
                @click="store.setType(t.value)"
              >{{ t.label }}</button>
            </div>
            <span class="mx-0.5 h-5 w-px shrink-0 bg-ink/10" aria-hidden="true" />
            <div class="inline-flex items-center gap-1" role="group" aria-label="签到状态筛选">
              <span class="px-1.5 text-[10.5px] font-medium text-ink-muted">状态</span>
              <button
                v-for="s in statusTabs"
                :key="`st-${s.value}`"
                type="button"
                :title="s.title"
                :aria-pressed="statusFilter === s.value"
                class="whitespace-nowrap rounded-lg px-2 py-1.5 text-[13px] font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
                :class="statusFilter === s.value ? 'bg-white text-brand shadow-sm ring-1 ring-ink/5' : 'text-ink-muted hover:text-ink-soft'"
                @click="store.setStatus(s.value)"
              >{{ s.label }}</button>
            </div>
            <span class="mx-0.5 h-5 w-px shrink-0 bg-ink/10" aria-hidden="true" />
            <BaseDatePicker range :from="dateFrom" :to="dateTo" placeholder="日期范围" @change="applyDateRange" />
          </div>
          <button
            type="button"
            class="ml-auto grid h-9 w-9 place-items-center rounded-xl border border-ink/10 bg-white text-ink-muted transition hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30 disabled:opacity-50"
            aria-label="刷新"
            :disabled="loadingRecords"
            @click="store.refresh"
          >
            <Icon name="refresh" :size="16" :class="loadingRecords && 'spin-refresh'" />
          </button>
        </div>

        <!-- 列表体 -->
        <div
          class="xb-scroll min-h-0 flex-1 overflow-y-auto px-2 transition-opacity sm:px-3"
          :class="refreshingRecords && 'opacity-60 pointer-events-none'"
          style="scrollbar-gutter: stable"
        >
          <!-- 未选中账号 -->
          <div v-if="!loadingTree && !selectedAccount" class="flex h-full min-h-[320px] flex-col items-center justify-center gap-3 text-center text-ink-muted">
            <span class="grid h-12 w-12 place-items-center rounded-2xl bg-cloud">
              <Icon name="records" :size="22" class="opacity-60" />
            </span>
            <div class="space-y-1">
              <p class="text-sm font-medium text-ink-soft">选一个账号开始核查</p>
              <p class="text-xs">{{ tree.length ? '左侧列出全站用户与其 B 平台账号。' : '全站暂无 B 平台账号。' }}</p>
            </div>
          </div>

          <!-- 首载骨架：与真实行同构，换新时不跳动（翻页/筛选走静默刷新） -->
          <div v-else-if="loadingRecords" class="space-y-3 px-1.5 py-3 sm:px-2">
            <div v-for="i in 4" :key="i" class="flex items-center gap-3">
              <span class="xb-skel h-8 w-[3px] shrink-0 rounded-full bg-ink/10" />
              <div class="flex-1 space-y-1.5">
                <div class="xb-skel h-3.5 w-40 rounded bg-ink/5 animate-pulse" />
                <div class="xb-skel h-3 w-56 rounded bg-ink/5 animate-pulse" />
              </div>
              <div class="xb-skel h-3 w-12 shrink-0 rounded bg-ink/5 animate-pulse" />
            </div>
          </div>

          <!-- 空态：说明为什么空，并给出一步可做的动作 -->
          <div v-else-if="pagedRows.length === 0" class="flex min-h-[320px] flex-col items-center justify-center gap-3 px-4 py-6 text-center text-ink-muted">
            <span class="grid h-12 w-12 place-items-center rounded-2xl bg-cloud">
              <Icon name="records" :size="22" class="opacity-60" />
            </span>
            <div class="space-y-1">
              <p class="text-sm font-medium text-ink-soft">{{ hasFilter ? '没有符合条件的记录' : '该账号暂无历史签到任务' }}</p>
              <p class="text-xs">{{ hasFilter ? '换个类型、状态或日期范围再试试。' : 'B 平台还没有下发过签到任务。' }}</p>
            </div>
            <button
              v-if="hasFilter"
              type="button"
              class="mt-1 inline-flex h-8 items-center rounded-lg border border-ink/10 px-3 text-xs font-medium text-ink-soft transition hover:bg-cloud hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
              @click="clearAllFilters"
            >
              清除全部筛选
            </button>
          </div>

          <!-- 任务行：可展开，详情复用 TaskDetailPanel -->
          <ul v-else ref="listRef" class="divide-y divide-ink/5">
            <li v-for="row in pagedRows" :key="row.id" data-task-row class="relative">
              <!-- 账本色带：贯穿行与展开区，沿左缘竖读即可看出该账号的合规走势 -->
              <span
                class="pointer-events-none absolute inset-y-0 left-0 w-[3px]"
                :class="row.finished ? 'bg-success/70' : 'bg-danger/70'"
                aria-hidden="true"
              />
              <button
                type="button"
                class="flex w-full items-center gap-3 py-3 pl-3 pr-2 text-left transition hover:bg-cloud/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand/30 sm:pl-4 sm:pr-3"
                @click="store.toggleExpand(row)"
              >
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="truncate text-[15px] font-semibold text-ink">{{ row.taskName }}</span>
                    <span class="shrink-0 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11px] font-medium" :class="typeBadge(row.type).cls">
                      {{ typeBadge(row.type).label }}
                    </span>
                    <span v-if="row.needPhoto" class="inline-flex shrink-0 items-center gap-1 whitespace-nowrap text-[11px] font-medium text-amber">
                      <Icon name="image" :size="12" />需拍照
                    </span>
                  </div>
                  <div class="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12px] text-ink-muted">
                    <span class="tabular-nums">
                      {{ row.startDate }}<template v-if="row.endDate && row.endDate !== row.startDate"> ~ {{ row.endDate }}</template>
                    </span>
                    <span class="text-ink/20" aria-hidden="true">·</span>
                    <span class="tabular-nums">{{ row.startTime }}<template v-if="row.endTime"> – {{ row.endTime }}</template></span>
                    <span class="text-ink/20" aria-hidden="true">·</span>
                    <span class="truncate">发起人 {{ row.initiator || '—' }}</span>
                  </div>
                </div>

                <!-- 签到状态：由色带承担强信号，此处只作文字确认（圆点 + 文字） -->
                <span
                  class="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap text-xs font-medium"
                  :class="row.finished ? 'text-success' : 'text-danger'"
                >
                  <span class="h-1.5 w-1.5 rounded-full" :class="row.finished ? 'bg-success' : 'bg-danger'" />
                  {{ row.finished ? '已签到' : '未签到' }}
                </span>

                <Icon
                  name="chevron-right"
                  :size="18"
                  class="shrink-0 text-ink-muted/70 transition-transform"
                  :class="detailOf(row) && detailOf(row).open ? 'rotate-90' : ''"
                />
              </button>

              <!-- 展开详情：任务要素 + 地理围栏 + 签到凭证（与用户端同款组件；py-4 与折叠补间 pad 对齐，勿改） -->
              <Transition :css="false" @enter="onDetailEnter" @leave="onDetailLeave">
                <div v-if="detailOf(row) && detailOf(row).open" class="overflow-hidden border-t border-ink/5 bg-cloud/30 py-4 pl-3 pr-2 sm:pl-4 sm:pr-3">
                  <TaskDetailPanel :detail="detailOf(row)" :row="row" @preview="openPreview" />
                </div>
              </Transition>
            </li>
          </ul>
        </div>

        <!-- 分页 -->
        <div v-if="total > 0" class="shrink-0 border-t border-ink/5 px-4 py-2.5 sm:px-5">
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
    </div>

    <!-- 底部间距占位：真实在流子元素，盒高计入 scrollHeight；
         -mt-4 sm:-mt-6 抵消根容器 gap，确保底部间距与其他页面一致（24px） -->
    <div class="h-6 shrink-0 -mt-4 sm:-mt-6" aria-hidden="true"></div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { gsap } from 'gsap'
// PhotoSwipe 与图库/用户端记录页同款（样式已在 main.js 全局引入）
import PhotoSwipeLightbox from 'photoswipe/lightbox'
import PhotoSwipe from 'photoswipe'
import { useSiteRecordsStore } from '@/stores/siteRecords'
import Icon from '@/components/Icon.vue'
import BasePagination from '@/components/BasePagination.vue'
import BaseDatePicker from '@/components/BaseDatePicker.vue'
import AccountTree from '@/components/siterecords/AccountTree.vue'
import TaskDetailPanel from '@/components/signrecords/TaskDetailPanel.vue'
import { useCollapseTransition } from '@/composables/useCollapseTransition'

const store = useSiteRecordsStore()
const {
  tree,
  selectedAccount,
  typeFilter,
  statusFilter,
  dateFrom,
  dateTo,
  page,
  pageSize,
  total,
  overview,
  loadingTree,
  loadingRecords,
  refreshingRecords,
} = storeToRefs(store)

const pagedRows = computed(() => store.tasks)

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

// 空态是否需要「清除筛选」出口；重置走 store.loadRecords 一次整备（避免逐个 setter 连发三次请求）
const hasFilter = computed(
  () => typeFilter.value !== 'all' || statusFilter.value !== 'all' || !!dateFrom.value || !!dateTo.value
)
function clearAllFilters() {
  typeFilter.value = 'all'
  statusFilter.value = 'all'
  dateFrom.value = null
  dateTo.value = null
  void store.loadRecords()
}

// 日期区间选择器回调：两端都空走 clearDateRange（内部有"本就为空则不发请求"的短路），
// 单边或双边有值都交给 setDateRange 统一处理（起止倒置由 store 交换）
function applyDateRange({ from, to }) {
  if (!from && !to) store.clearDateRange()
  else store.setDateRange(from, to)
}

function typeBadge(t) {
  if (t === 'activity') return { label: '活动签到', cls: 'bg-info/10 text-info' }
  if (t === 'dorm') return { label: '寝室签到', cls: 'bg-brand/10 text-brand' }
  return { label: '通用账号', cls: 'bg-ink/5 text-ink-soft' }
}

function detailOf(row) {
  return store.getDetail(row.id)
}

// ---- 行错落入场（对齐用户端记录页；尊重系统「减少动态效果」偏好） ----
const reduceMotion = ref(false)
let mm = null
const listRef = ref(null)

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

// 详情高度补间：纵向 padding 与 height 一起归零并 clearProps（抽到组合式共用）
const { onEnter: onDetailEnter, onLeave: onDetailLeave } = useCollapseTransition(
  () => reduceMotion.value,
  { pad: 16 } // 与模板 py-4 对齐
)

watch([page, statusFilter, typeFilter, dateFrom, dateTo], async () => {
  await nextTick()
  staggerRows()
})
watch(loadingRecords, async (v) => {
  if (v) return
  await nextTick()
  staggerRows()
})

onMounted(() => {
  mm = gsap.matchMedia()
  mm.add('(prefers-reduced-motion: reduce)', () => {
    reduceMotion.value = true
    return () => {
      reduceMotion.value = false
    }
  })
  store.loadTree()
})

onUnmounted(() => {
  mm?.revert()
  lightbox?.destroy()
  if (listRef.value) gsap.killTweensOf(listRef.value.querySelectorAll('[data-task-row]'))
})

// ---- 签到照片全屏（复用图库同款 PhotoSwipe；v5 必须显式 width/height） ----
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
  lightbox?.destroy()
  const { width, height } = await probeSize(log.imageUrl)
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
</script>

<style scoped>
.xb-scroll {
  scrollbar-gutter: stable;
}
/* 仅让刷新图标旋转，按钮容器与其它元素保持静止 */
.spin-refresh { animation: xb-spin 0.8s linear infinite; }
@keyframes xb-spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
  .spin-refresh { animation: none; }
  /* 骨架屏脉冲在减弱动效偏好下退化为静态灰块 */
  .xb-skel { animation: none; }
}
</style>
