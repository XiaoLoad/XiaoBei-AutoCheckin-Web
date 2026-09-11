<template>
  <div class="flex flex-col gap-4 sm:gap-5 lg:flex-1 lg:min-h-0">
    <div class="page-desc shrink-0 text-[13px] text-ink-muted">
      左侧账号树定位「哪个用户的哪个 B 平台账号」，右侧查看该账号在 B 平台的历史签到记录，行可展开看围栏与凭证详情。
    </div>

    <div class="flex flex-col gap-4 lg:min-h-0 lg:flex-row">
      <!-- ============ 左：账号树 ============ -->
      <AccountTree class="max-h-[560px] shrink-0 rounded-2xl border border-ink/5 bg-card shadow-[0_1px_2px_rgba(20,33,61,0.04),0_10px_28px_-16px_rgba(20,33,61,0.18)] lg:max-h-[calc(100vh-13rem)] lg:w-[336px]" />

      <!-- ============ 右：签到记录区 ============ -->
      <div class="dash-card flex min-h-[520px] flex-col overflow-hidden lg:min-w-0 lg:flex-1">
        <!-- 上下文条：所选账号 + 验证状态 + 全历史统计 -->
        <div class="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-2 border-b border-ink/5 px-4 py-3 sm:px-5">
          <template v-if="selectedAccount">
            <h3 class="text-[15px] font-bold text-ink">
              {{ selectedAccount.account }}
              <template v-if="selectedAccount.profile && selectedAccount.profile.name">
                · {{ selectedAccount.profile.name }}
              </template>
            </h3>
            <span class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium" :class="typeBadge(selectedAccount.type).cls">
              {{ typeBadge(selectedAccount.type).label }}
            </span>
            <span
              class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium"
              :class="selectedAccount.verifyStatus === 'ok' ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'"
            >
              {{ selectedAccount.verifyStatus === 'ok' ? '验证正常' : '凭证异常' }}
            </span>
            <span class="hidden items-center gap-1 rounded-full bg-cloud px-2.5 py-1 text-[11.5px] text-ink-soft sm:inline-flex">
              所属用户 <b class="font-semibold text-ink">{{ selectedAccount.owner }}</b>
            </span>
          </template>
          <h3 v-else class="text-[15px] font-bold text-ink">签到记录</h3>

          <!-- 统计 chips：全历史口径（后端 overview），跟随类型/状态筛选 -->
          <div class="ml-auto flex flex-wrap items-center gap-2">
            <span class="schip inline-flex items-center gap-1 rounded-full bg-cloud px-2.5 py-1 text-[11.5px] text-ink-soft">总任务 <b class="tabular-nums">{{ overview.total }}</b></span>
            <span class="schip inline-flex items-center gap-1 rounded-full bg-cloud px-2.5 py-1 text-[11.5px] text-ink-soft">已签 <b class="tabular-nums text-success">{{ overview.finished }}</b></span>
            <span class="schip inline-flex items-center gap-1 rounded-full bg-cloud px-2.5 py-1 text-[11.5px] text-ink-soft">未签 <b class="tabular-nums text-danger">{{ overview.unsigned }}</b></span>
            <span class="schip inline-flex items-center gap-1 rounded-full bg-cloud px-2.5 py-1 text-[11.5px] text-ink-soft">满勤率 <b class="tabular-nums">{{ overview.rate }}%</b></span>
          </div>
        </div>

        <!-- 筛选工具条：类型 / 状态双胶囊 + 刷新（与用户端签到记录页同款交互） -->
        <div class="flex shrink-0 flex-wrap items-center gap-2 border-b border-ink/5 px-4 py-2.5 sm:px-5">
          <div class="inline-flex items-center gap-1 rounded-xl bg-cloud p-1">
            <span class="px-1.5 text-[11px] font-medium text-ink-muted">类型</span>
            <button
              v-for="t in typeTabs"
              :key="`ty-${t.value}`"
              type="button"
              class="whitespace-nowrap rounded-lg px-2.5 py-1.5 text-sm font-medium transition"
              :class="typeFilter === t.value ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
              @click="store.setType(t.value)"
            >{{ t.label }}</button>
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
            >{{ s.label }}</button>
          </div>
          <span class="h-5 w-px bg-ink/10" aria-hidden="true" />
          <div class="inline-flex items-center gap-1 rounded-xl bg-cloud p-1">
            <span class="px-1.5 text-[11px] font-medium text-ink-muted">日期</span>
            <input
              v-model="dateFrom"
              type="date"
              class="w-[118px] rounded-lg bg-transparent px-1 py-1 text-xs text-ink-soft outline-none tabular-nums"
              :max="dateTo || undefined"
              title="起始日期（任务区间与窗口重叠即入选）"
              @change="store.setDateRange(dateFrom, dateTo)"
            />
            <span class="text-[11px] text-ink-muted">~</span>
            <input
              v-model="dateTo"
              type="date"
              class="w-[118px] rounded-lg bg-transparent px-1 py-1 text-xs text-ink-soft outline-none tabular-nums"
              :min="dateFrom || undefined"
              title="结束日期（任务区间与窗口重叠即入选）"
              @change="store.setDateRange(dateFrom, dateTo)"
            />
            <button
              v-if="dateFrom || dateTo"
              type="button"
              class="grid h-6 w-6 place-items-center rounded-lg text-ink-muted transition hover:bg-white hover:text-ink"
              title="清除日期筛选"
              @click="store.clearDateRange"
            >
              <Icon name="x-circle" :size="14" />
            </button>
          </div>
          <button
            type="button"
            class="ml-auto grid h-9 w-9 place-items-center rounded-xl border border-ink/10 text-ink-muted transition hover:bg-cloud hover:text-ink"
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
          <div v-if="!loadingTree && !selectedAccount" class="flex h-full min-h-[320px] flex-col items-center justify-center gap-2 text-ink-muted">
            <Icon name="records" :size="32" class="opacity-40" />
            <p class="text-sm">{{ tree.length ? '在左侧账号树中选择一个 B 平台账号' : '全站暂无 B 平台账号' }}</p>
          </div>

          <!-- 加载中（仅首载；翻页/筛选静默换新） -->
          <div v-else-if="loadingRecords" class="flex items-center justify-center py-16 text-sm text-ink-muted">
            加载中…
          </div>

          <!-- 空态 -->
          <div v-else-if="pagedRows.length === 0" class="flex min-h-[320px] flex-col items-center justify-center gap-3 py-6 text-ink-muted">
            <Icon name="records" :size="34" class="opacity-40" />
            <p class="text-sm font-medium text-ink-soft">暂无数据</p>
            <p class="text-xs">当前账号与筛选条件下还没有历史签到任务</p>
          </div>

          <!-- 任务行（可展开，详情复用 TaskDetailPanel） -->
          <ul v-else ref="listRef" class="divide-y divide-ink/5">
            <li v-for="row in pagedRows" :key="row.id" data-task-row>
              <button
                type="button"
                class="flex w-full items-center gap-3 px-2 py-3 text-left transition hover:bg-cloud/40 sm:px-3"
                @click="store.toggleExpand(row)"
              >
                <!-- 状态色条：纵向扫读的第一视觉锚点 -->
                <span class="h-9 w-1 shrink-0 rounded-full" :class="row.finished ? 'bg-success' : 'bg-danger'" />

                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="truncate text-[15px] font-semibold text-ink">{{ row.taskName }}</span>
                    <span class="shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium" :class="typeBadge(row.type).cls">
                      {{ typeBadge(row.type).label }}
                    </span>
                    <span v-if="row.needPhoto" class="shrink-0 whitespace-nowrap rounded-full bg-amber/10 px-2 py-0.5 text-xs font-medium text-amber">需拍照</span>
                  </div>
                  <div class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
                    <span class="tabular-nums">{{ row.startDate }}<template v-if="row.endDate && row.endDate !== row.startDate"> ~ {{ row.endDate }}</template></span>
                    <span class="tabular-nums">{{ row.startTime }}<template v-if="row.endTime"> – {{ row.endTime }}</template></span>
                    <span class="truncate">发起人 {{ row.initiator || '—' }}</span>
                  </div>
                </div>

                <span class="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium" :class="statusBadge(row.finished).cls">
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

              <!-- 展开详情：任务要素 + 地理围栏 + 签到凭证（与用户端同款组件） -->
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
    </div>

    <!-- 底部间距占位：真实在流子元素，盒高计入 scrollHeight -->
    <div class="h-6 shrink-0" aria-hidden="true"></div>
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

function typeBadge(t) {
  if (t === 'activity') return { label: '活动签到', cls: 'bg-info/10 text-info' }
  if (t === 'dorm') return { label: '寝室签到', cls: 'bg-brand/10 text-brand' }
  return { label: '通用账号', cls: 'bg-ink/5 text-ink-soft' }
}

function statusBadge(finished) {
  return finished
    ? { label: '已签到', cls: 'bg-success/10 text-success', dot: 'bg-success' }
    : { label: '未签到', cls: 'bg-danger/10 text-danger', dot: 'bg-danger' }
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
</style>
