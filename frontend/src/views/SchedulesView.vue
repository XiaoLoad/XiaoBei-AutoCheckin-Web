<template>
  <div class="flex flex-1 min-h-0 flex-col gap-6">
    <!-- 概览卡 -->
    <div class="dash-card fade-up shrink-0 p-4 sm:p-5">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div class="min-w-0">
          <h2 class="text-lg font-semibold text-ink">定时任务</h2>
          <p class="mt-1 text-sm text-ink-muted">为已配置的平台账号开启定时签到，调度器将按计划自动执行。</p>
        </div>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div class="rounded-xl bg-cloud/50 px-4 py-3 text-right sm:text-left">
            <p class="text-2xl font-semibold tabular-nums text-brand">{{ store.stats.enabled }}</p>
            <p class="text-xs text-ink-muted">运行中</p>
          </div>
          <div class="rounded-xl bg-cloud/50 px-4 py-3 text-right sm:text-left">
            <p class="text-2xl font-semibold tabular-nums text-ink">{{ store.stats.total }}</p>
            <p class="text-xs text-ink-muted">任务总数</p>
          </div>
          <div class="rounded-xl bg-cloud/50 px-4 py-3 text-right sm:text-left">
            <p class="text-2xl font-semibold tabular-nums text-ink">{{ store.stats.dormEnabled }}</p>
            <p class="text-xs text-ink-muted">寝室签到（运行中）</p>
          </div>
          <div class="rounded-xl bg-cloud/50 px-4 py-3 text-right sm:text-left">
            <p class="text-2xl font-semibold tabular-nums text-ink">{{ store.stats.activityEnabled }}</p>
            <p class="text-xs text-ink-muted">活动签到（运行中）</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 列表卡片：搜索 + 类型切换头部 + 独立滚动列表 + 固定底部分页，合并为单一模块 -->
    <div class="dash-card fade-up flex flex-1 min-h-0 flex-col overflow-hidden rounded-2xl">
      <!-- 头部：账号模糊搜索 + 类型切换，与下方列表用分隔线隔开 -->
      <div class="flex flex-wrap items-center gap-x-4 gap-y-3 border-b border-ink/10 px-4 py-3">
        <!-- 账号模糊搜索框：按姓名 / 学号 / 班级 匹配 -->
        <div class="relative w-56 sm:w-72">
          <Icon name="search" :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索姓名 / 学号 / 班级"
            class="h-9 w-full rounded-lg border border-ink/10 bg-white pl-9 pr-8 text-sm text-ink outline-none transition placeholder:text-ink-muted focus:border-brand/50 focus:ring-2 focus:ring-brand/15"
          />
          <button
            v-if="searchQuery"
            type="button"
            class="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 text-ink-muted transition hover:bg-cloud hover:text-ink"
            aria-label="清空搜索"
            @click="searchQuery = ''"
          >
            <Icon name="x-circle" :size="15" />
          </button>
        </div>

        <!-- 运行状态筛选 -->
        <div class="w-32">
          <BaseSelect v-model="runFilter" :options="runOptions" size="sm" placeholder="运行状态" />
        </div>

        <!-- 账号状态筛选 -->
        <div class="w-32">
          <BaseSelect v-model="accountStatusFilter" :options="accountStatusOptions" size="sm" placeholder="账号状态" />
        </div>

        <!-- 类型切换 -->
        <div class="ml-auto inline-flex items-center rounded-xl bg-cloud p-1">
          <button
            v-for="t in typeTabs"
            :key="t.value"
            type="button"
            class="rounded-lg px-3 py-1.5 text-sm font-medium transition"
            :class="typeFilter === t.value ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
            @click="typeFilter = t.value"
          >
            {{ t.label }}
          </button>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="store.loading" class="flex flex-1 items-center justify-center text-ink-muted">加载中…</div>

      <!-- 完全无任务：引导到签到配置 · 账号任务配置 Tab 添加 -->
      <div v-else-if="store.schedules.length === 0" class="flex flex-1 flex-col items-center justify-center gap-3 text-ink-muted">
        <Icon name="clock" :size="32" class="opacity-50" />
        <span>还没有定时任务，请先在「签到配置 · 账号任务配置」中添加</span>
        <button
          type="button"
          class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark"
          @click="goToSignConfig"
        >
          前往签到配置
        </button>
      </div>

      <!-- 筛选后无结果 -->
      <div v-else-if="filtered.length === 0" class="flex flex-1 flex-col items-center justify-center gap-2 text-ink-muted">
        <Icon name="clock" :size="30" class="opacity-50" />
        <span>没有符合条件的定时任务</span>
      </div>

      <!-- 卡片网格：独立滚动区域 -->
      <div v-else class="xb-scroll min-h-0 flex-1 overflow-auto">
        <div ref="grid" class="grid grid-cols-1 gap-3 p-3 sm:grid-cols-2 xl:grid-cols-3">
          <ScheduleCard
            v-for="s in paged"
            :key="s.id"
            :schedule="s"
            :config-meta="store.configMetaOf(s.accountId, s.taskType)"
            @toggle="store.toggle"
            @open-settings="openDrawer"
            @delete="store.removeTask"
          />
        </div>
      </div>

      <!-- 分页：常显（单页也显示，便于切换每页条数），固定列表底部 -->
      <BasePagination
        v-if="!store.loading && filtered.length > 0"
        class="shrink-0 border-t border-ink/10 px-4 py-3"
        :page="page"
        :page-size="pageSize"
        :total="total"
        @update:page="page = $event"
        @update:page-size="pageSize = $event"
      />
    </div>

    <!-- 底部间距占位 -->
    <div class="h-6 shrink-0 -mt-6" aria-hidden="true" />

    <!-- 定时设置抽屉 -->
    <ScheduleSettingsDrawer
      v-if="drawerSchedule"
      :schedule="drawerSchedule"
      :saving="store.saving"
      @save="onSave"
      @close="drawerSchedule = null"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { gsap } from 'gsap'
import { useRouter } from 'vue-router'
import { useSchedulesStore } from '@/stores/schedules'
import { useSignConfigStore } from '@/stores/signConfig'
import ScheduleCard from '@/components/schedules/ScheduleCard.vue'
import ScheduleSettingsDrawer from '@/components/schedules/ScheduleSettingsDrawer.vue'
import BasePagination from '@/components/BasePagination.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import Icon from '@/components/Icon.vue'

const store = useSchedulesStore()
const signConfigStore = useSignConfigStore()
const router = useRouter()
// 空态引导：跳转至「签到配置 · 账号任务配置」Tab 添加定时任务
function goToSignConfig() {
  signConfigStore.setActiveTab('tasks')
  router.push({ name: 'sign-config' })
}
const grid = ref(null)
const searchQuery = ref('')
const typeFilter = ref('all')
const runFilter = ref('all')
const accountStatusFilter = ref('all')
const drawerSchedule = ref(null)

const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

const typeTabs = [
  { label: '全部', value: 'all' },
  { label: '寝室签到', value: 'dorm' },
  { label: '活动签到', value: 'activity' }
]

// 状态筛选下拉选项
const runOptions = [
  { label: '全部状态', value: 'all' },
  { label: '运行中', value: 'running' },
  { label: '未运行', value: 'stopped' }
]
const accountStatusOptions = [
  { label: '全部账号', value: 'all' },
  { label: '已启用', value: 'enabled' },
  { label: '未启用', value: 'disabled' }
]

// 账号模糊搜索 + 类型 + 运行状态 + 账号状态 组合筛选
const filtered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return store.schedules.filter((s) => {
    if (typeFilter.value !== 'all' && s.taskType !== typeFilter.value) return false
    if (runFilter.value !== 'all') {
      const running = s.enabled
      if (runFilter.value === 'running' && !running) return false
      if (runFilter.value === 'stopped' && running) return false
    }
    if (accountStatusFilter.value !== 'all') {
      const accOn = s.accountEnabled
      if (accountStatusFilter.value === 'enabled' && !accOn) return false
      if (accountStatusFilter.value === 'disabled' && accOn) return false
    }
    if (q) {
      const hay = [s.accountName, s.studentNo, s.className].filter(Boolean).join(' ').toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

// 分页：过滤后的列表再分页（默认每页 10，可按 BasePagination 调整）
const page = ref(1)
const pageSize = ref(10)
const total = computed(() => filtered.value.length)
const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

function openDrawer(schedule) {
  drawerSchedule.value = schedule
}
function onSave(id, patch) {
  store.saveSettings(id, patch)
}

// GSAP 错峰入场：卡片依次淡入上移
function staggerIn() {
  if (prefersReduced || !grid.value) return
  const cards = grid.value.querySelectorAll('.sched-card')
  if (!cards.length) return
  gsap.fromTo(
    cards,
    { opacity: 0, y: 14 },
    { opacity: 1, y: 0, duration: 0.42, ease: 'power2.out', stagger: 0.05, clearProps: 'opacity,transform' }
  )
}

onMounted(async () => {
  await store.load()
  // 配置套元信息（关联配置名/位置/时段）供卡片与抽屉预览使用；未加载则按需拉取一次
  if (!signConfigStore.accounts.length && !signConfigStore.loading) {
    await signConfigStore.load()
  }
  await nextTick()
  staggerIn()
})

// 筛选变化：重置到首页并轻量重入场
watch([searchQuery, typeFilter, runFilter, accountStatusFilter], async () => {
  page.value = 1
  await nextTick()
  staggerIn()
})

// 翻页 / 改每页条数：页码越界夹紧，并重放入场动画
watch([page, pageSize], async () => {
  const tp = Math.max(1, Math.ceil(total.value / pageSize.value))
  if (page.value > tp) page.value = tp
  await nextTick()
  staggerIn()
})
</script>

<style scoped>
.xb-scroll {
  scrollbar-gutter: stable;
}
</style>

