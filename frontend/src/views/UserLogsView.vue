<template>
  <div class="flex flex-col gap-6 lg:flex-1 lg:min-h-0">
    <!-- 指标：今日脉搏，全表口径 —— 不随筛选收缩。
         这四个数回答的是「今天这个平台还健康吗」，而筛选是在追问历史，两者不该互相牵制。 -->
    <div class="grid shrink-0 grid-cols-2 gap-4 lg:grid-cols-4">
      <StatCard
        label="今日登录"
        :value="metrics.loginToday"
        unit="次"
        icon="user-check"
        tone="brand"
        :loading="!store.summaryLoaded"
        count-up
      />
      <StatCard
        label="登录失败"
        :value="metrics.loginFailToday"
        unit="次"
        icon="x-circle"
        tone="danger"
        :loading="!store.summaryLoaded"
        count-up
      />
      <StatCard
        label="权限与额度变更"
        :value="metrics.userChangeToday"
        unit="次"
        icon="users"
        tone="amber"
        :loading="!store.summaryLoaded"
        count-up
      />
      <StatCard
        label="进行中会话"
        :value="metrics.ongoingSessions"
        unit="个"
        icon="clock"
        tone="info"
        :loading="!store.summaryLoaded"
        count-up
      />
    </div>

    <!-- 异常提醒：放在指标行正下方，而不是吊在页面最底。
         告警得先被看见才有意义——需要滚到底才能发现的告警等于没有。 -->
    <section
      v-if="store.anomalies.length"
      class="fade-up shrink-0 rounded-2xl border border-danger/20 bg-danger/[0.05] px-4 py-3 sm:px-5"
    >
      <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span class="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-danger/10 text-danger">
          <Icon name="alert" :size="15" />
        </span>
        <p class="text-sm font-medium text-ink">
          近 {{ store.anomalyWindowDays }} 天有
          <span class="tabular-nums">{{ store.anomalies.length }}</span>
          个来源 IP 连续登录失败，均未建立会话
        </p>
        <span
          class="shrink-0 rounded-full bg-danger/10 px-2 py-0.5 text-[11px] font-medium text-danger"
        >
          需关注
        </span>
        <button
          type="button"
          class="ml-auto inline-flex shrink-0 items-center gap-1 rounded-lg px-1.5 py-1 text-xs font-medium text-brand transition hover:bg-white/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
          @click="showAnomalies = !showAnomalies"
        >
          {{ showAnomalies ? '收起明细' : `展开 ${store.anomalies.length} 条明细` }}
          <Icon
            name="chevron-down"
            :size="13"
            class="transition-transform duration-200"
            :class="showAnomalies ? 'rotate-180' : ''"
          />
        </button>
      </div>

      <!-- 明细：每条一个胶囊，横向流动，通常两三行内看完；
           点一下就按该 IP 反查流水，把告警变成可追查的入口。
           胶囊数量随数据变，展开时按高度补间而不是瞬时弹开——骤然的位移会把刚读到的行顶走 -->
      <Transition :css="false" @enter="onAnomalyEnter" @leave="onAnomalyLeave">
        <div v-if="showAnomalies" class="mt-2.5 flex flex-wrap gap-2">
          <button
            v-for="a in store.anomalies"
            :key="a.ip"
            data-detail-item
            type="button"
            class="inline-flex max-w-full flex-wrap items-center gap-x-2 gap-y-1 rounded-xl border border-danger/15 bg-white px-2.5 py-1.5 text-left text-xs transition hover:border-danger/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
            @click="onInspectIp(a.ip)"
          >
            <!-- ⚠️IP 同样不用 font-mono：与胶囊里其余文字（正文族）字形盒高度不同，
                 同一行高下基线会错开约 1px（详见 OpSessionCard.vue 同处注释），
                 tabular-nums 已足够让点位对齐 -->
            <span class="tabular-nums text-ink">{{ a.ip }}</span>
            <span class="text-ink/20">·</span>
            <span class="tabular-nums text-ink-muted">{{ a.firstAt }} → {{ a.lastAt }}</span>
            <span class="text-ink/20">·</span>
            <span class="text-ink-muted">
              失败 <b class="tabular-nums text-danger">{{ a.count }}</b> 次
            </span>
            <template v-if="a.accounts.length">
              <span class="text-ink/20">·</span>
              <span class="truncate text-ink-muted">尝试账号 {{ a.accounts.join('、') }}</span>
            </template>
            <span class="font-medium text-brand">筛选该 IP</span>
          </button>
        </div>
      </Transition>
    </section>

    <!-- 筛选：单行铺开（窄屏自然折行）。
         ⚠️搜索框必须定宽——用 flex-1 会吃掉整行剩余空间，把后面的下拉与日期挤到下一行 -->
    <div class="dash-card fade-up relative z-30 shrink-0 p-3 sm:p-4">
      <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
        <!-- 单框三用（用户名 / IP / 事由）：界面只留一个搜索框，而这三者是同一类追问。
             右侧清除钮固定占位（pr-9），有无内容都不改变输入框尺寸，免得一打字就抖 -->
        <div class="relative w-56 md:w-64">
          <Icon
            name="search"
            :size="15"
            class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink/30"
          />
          <input
            v-model="keywordDraft"
            type="text"
            placeholder="搜索用户名、IP 或事由"
            class="h-9 w-full rounded-xl border border-ink/10 bg-white pl-9 pr-9 text-sm text-ink outline-none transition placeholder:text-ink/35 focus:border-brand focus:ring-4 focus:ring-brand/10"
          />
          <button
            v-if="keywordDraft"
            type="button"
            class="absolute right-2 top-1/2 grid h-5 w-5 -translate-y-1/2 place-items-center rounded-md text-ink/35 transition hover:bg-cloud hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
            aria-label="清除搜索"
            title="清除搜索"
            @click="onClearKeyword"
          >
            <Icon name="close" :size="13" />
          </button>
        </div>
        <div class="w-36 sm:w-40">
          <BaseSelect
            :model-value="store.filters.action"
            :options="actionOptions"
            :searchable="false"
            size="sm"
            @update:model-value="(v) => store.applyFilter({ action: v })"
          />
        </div>
        <div class="w-28 sm:w-32">
          <BaseSelect
            :model-value="store.filters.result"
            :options="resultOptions"
            :searchable="false"
            size="sm"
            @update:model-value="(v) => store.applyFilter({ result: v })"
          />
        </div>

        <BaseDatePicker
          range
          :from="store.filters.dateFrom"
          :to="store.filters.dateTo"
          @change="onDateChange"
        />

        <div class="inline-flex items-center rounded-xl bg-cloud p-1">
          <button
            v-for="q in quickRanges"
            :key="q.key"
            type="button"
            class="whitespace-nowrap rounded-lg px-2 py-1.5 text-sm font-medium transition"
            :class="
              store.quickRange === q.key
                ? 'bg-white text-brand shadow-sm'
                : 'text-ink-muted hover:text-ink-soft'
            "
            @click="store.setQuickRange(q.key)"
          >
            {{ q.label }}
          </button>
        </div>

        <div class="ml-auto flex items-center gap-2">
          <button
            v-if="store.hasFilter"
            type="button"
            class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-xl border border-ink/10 bg-white px-3 py-1.5 text-sm font-medium text-ink-soft transition hover:border-ink/20 hover:text-ink"
            @click="onReset"
          >
            <Icon name="refresh" :size="14" />
            重置
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-xl border border-ink/10 bg-white px-3 py-1.5 text-sm font-medium text-ink-soft transition hover:border-brand/30 hover:text-brand disabled:cursor-not-allowed disabled:opacity-60"
            :disabled="store.exporting"
            @click="onExport"
          >
            <Icon name="file" :size="14" />
            {{ store.exporting ? '导出中…' : '导出 CSV' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 列表：会话与流水同源不同投影，共用一套筛选与分页 -->
    <div
      class="dash-card fade-up flex flex-col rounded-2xl lg:min-h-[480px] lg:flex-1"
      :class="store.refreshing && 'pointer-events-none opacity-60'"
    >
      <header
        class="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-ink/5 px-4 py-3 sm:px-5"
      >
        <!-- 会话 = 「他这次进来都干了什么」；流水 = 「某件事发生在什么时候」 -->
        <div class="inline-flex items-center rounded-xl bg-cloud p-1">
          <button
            v-for="v in viewTabs"
            :key="v.key"
            type="button"
            class="whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition"
            :class="
              store.view === v.key
                ? 'bg-white text-brand shadow-sm'
                : 'text-ink-muted hover:text-ink-soft'
            "
            @click="onViewSwitch(v.key)"
          >
            {{ v.label }}
          </button>
        </div>
        <p class="text-xs text-ink-muted">
          <template v-if="store.isSession">
            共 <b class="font-medium tabular-nums text-ink-soft">{{ store.sessionTotal }}</b> 段会话
          </template>
          <template v-else>
            共 <b class="font-medium tabular-nums text-ink-soft">{{ store.total }}</b> 条记录
          </template>
          · 保留 {{ store.retentionDays }} 天
        </p>
      </header>

      <div ref="bodyRef" class="px-4 py-3 sm:px-5 lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
        <!-- 首屏骨架：形态与真实内容一致，数据到位时列表不整体跳动 -->
        <div v-if="store.loading" class="flex flex-col gap-3">
          <template v-if="store.isSession">
            <div v-for="n in 3" :key="n" class="rounded-2xl border border-ink/5 p-3.5">
              <div class="flex items-center gap-2">
                <div class="h-4 w-20 animate-pulse rounded bg-ink/5" />
                <div class="h-4 w-14 animate-pulse rounded-full bg-ink/5" />
                <div class="ml-auto h-4 w-20 animate-pulse rounded-full bg-ink/5" />
              </div>
              <div class="mt-3 flex flex-col gap-2.5">
                <div v-for="m in 3" :key="m" class="h-3.5 animate-pulse rounded bg-ink/5" :class="m === 1 ? 'w-3/4' : 'w-1/2'" />
              </div>
            </div>
          </template>
          <template v-else>
            <div v-for="n in 6" :key="n" class="flex gap-3 py-1.5">
              <div class="h-3.5 w-10 shrink-0 animate-pulse rounded bg-ink/5" />
              <div class="flex-1 space-y-2">
                <div class="h-3.5 w-2/3 animate-pulse rounded bg-ink/5" />
                <div class="h-3 w-1/3 animate-pulse rounded bg-ink/5" />
              </div>
            </div>
          </template>
        </div>

        <div
          v-else-if="listCount === 0"
          class="flex min-h-[280px] flex-col items-center justify-center gap-2 py-8 text-center"
        >
          <span class="grid h-11 w-11 place-items-center rounded-full bg-cloud text-ink/40">
            <Icon name="shield" :size="20" />
          </span>
          <p class="text-sm font-medium text-ink">
            {{ store.hasFilter ? '没有符合条件的记录' : '暂无用户日志' }}
          </p>
          <p class="max-w-sm text-xs text-ink-muted">
            {{
              store.hasFilter
                ? '放宽筛选条件或调整日期区间后再试。'
                : '平台用户登录、退出以及权限与额度变更后，会在这里留下痕迹。'
            }}
          </p>
        </div>

        <!-- 会话视图：一段会话一张卡，时间轴只画在卡片内部 -->
        <div v-else-if="store.isSession" class="flex flex-col gap-3">
          <OpSessionCard v-for="s in store.sessions" :key="s.id" :session="s" />
        </div>

        <!-- 流水视图：按日分段，段内平铺事件，行与行之间**不画任何连线** -->
        <template v-else>
          <section v-for="g in store.groups" :key="g.day" class="py-1">
            <header class="flex items-center gap-3 py-1.5">
              <span class="h-1.5 w-1.5 shrink-0 rounded-sm bg-brand/50" aria-hidden="true" />
              <span class="shrink-0 font-mono text-[11px] tabular-nums text-ink-muted">
                {{ g.label }}
              </span>
              <span class="h-px flex-1 bg-ink/[0.08]" aria-hidden="true" />
            </header>
            <ol class="flex flex-col divide-y divide-ink/5">
              <OpLogEntry
                v-for="row in g.items"
                :key="row.id"
                :row="row"
                :open="store.expandedId === row.id"
                @toggle="store.toggleDetail"
              />
            </ol>
          </section>
        </template>
      </div>

      <footer v-if="listCount > 0" class="shrink-0 border-t border-ink/10 px-4 py-2.5 sm:px-5">
        <BasePagination
          :page="store.page"
          :page-size="store.pageSize"
          :total="listCount"
          :page-size-options="[10, 20, 50]"
          :disabled="store.loading"
          @update:page="store.setPage"
          @update:page-size="store.setPageSize"
        />
      </footer>
    </div>

    <!-- 底部占位：滚动容器的末端 padding 会被折叠，末端间距靠真实占位块兜住 -->
    <div class="h-6 shrink-0" aria-hidden="true" />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { gsap } from 'gsap'
import StatCard from '@/components/StatCard.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import BaseDatePicker from '@/components/BaseDatePicker.vue'
import BasePagination from '@/components/BasePagination.vue'
import Icon from '@/components/Icon.vue'
import OpLogEntry from '@/components/userlogs/OpLogEntry.vue'
import OpSessionCard from '@/components/userlogs/OpSessionCard.vue'
import { useOpLogsStore } from '@/stores/opLogs'
import { useCollapseTransition } from '@/composables/useCollapseTransition'
import { buildOpCsv, opActionMeta } from '@/utils/opLogMeta'
import { toast } from '@/utils/toast'

const store = useOpLogsStore()

const viewTabs = [
  { key: 'flow', label: '流水' },
  { key: 'session', label: '会话' },
]
const quickRanges = [
  { key: 'today', label: '今天' },
  { key: '7d', label: '7 天' },
  { key: '30d', label: '30 天' },
]

// 分页总数取自当前视图各自的口径（段数 vs 事件数），不能混用
const listCount = computed(() => (store.isSession ? store.sessionTotal : store.total))

// 指标行直接读这四张卡的取值（口径见后端 /op-logs/summary，恒为「今日」）
const metrics = computed(() => store.metrics)

// 动作下拉只列库里真实出现过的动作，并带上计数：没数据的项不必占位
const actionOptions = computed(() => [
  { value: '', label: '全部动作' },
  ...store.meta.actions.map((a) => ({
    value: a.value,
    label: `${opActionMeta(a.value).label}（${a.count}）`,
  })),
])

const resultOptions = [
  { value: '', label: '全部结果' },
  { value: 'success', label: '成功' },
  { value: 'fail', label: '失败' },
]

const keywordDraft = ref(store.filters.keyword)

// 异常明细默认展开：收起会把「哪台机器在试密码」藏起来，而那正是这条告警要传达的东西；
// 明细最多 5 条、按胶囊横排，占用高度可控
const showAnomalies = ref(true)

// 动效统一挂在这一处开关上：命中系统「减少动态效果」时所有补间直接落终态
const reduceMotion = ref(false)
let mm = null
const bodyRef = ref(null)

// 告警明细没有纵向内边距（靠 mt-2.5 拉开间距），故 pad 给 0，只补间高度
const { onEnter: onAnomalyEnter, onLeave: onAnomalyLeave } = useCollapseTransition(
  () => reduceMotion.value,
  { pad: 0, duration: 0.3 }
)

function onDateChange({ from, to }) {
  store.applyFilter({ dateFrom: from || '', dateTo: to || '' })
}

function onReset() {
  store.resetFilters()
  keywordDraft.value = ''
}

// 一键清除搜索：立刻清筛选值，不等防抖——防抖回调随后会发现「值已相同」而提前返回，不会多发请求
function onClearKeyword() {
  keywordDraft.value = ''
  if (store.filters.keyword) store.applyFilter({ keyword: '' })
}

// 视图切换要等新数据落地再播动画：切的那一刻屏上还是旧投影（或还没到的新数据），
// 那时候动的是错的东西。这里只记下「切了」，等列表换了引用再播。
let pendingView = ''

function onViewSwitch(key) {
  if (key === store.view) return
  pendingView = key
  store.setView(key)
}

// 列表入场：会话 ⇄ 流水是换一种看法，值得一次明确的转场；
// 翻页与改筛选刻意不播——那是换一屏数据，每翻一页重放动画只会把浏览节奏拖慢。
function playBodyEnter() {
  const el = bodyRef.value
  if (!el || reduceMotion.value) return
  gsap.fromTo(
    el,
    { autoAlpha: 0, y: 8 },
    {
      autoAlpha: 1,
      y: 0,
      duration: 0.3,
      ease: 'power2.out',
      overwrite: true,
      onComplete: () => gsap.set(el, { clearProps: 'opacity,visibility,transform' }),
    }
  )
}

// 点异常行即按该 IP 反查流水：告警条不只是提示，还得能顺着点进去。
// 先切视图再改筛选，末次请求才是最终状态的请求（竞态守卫只采纳最新一次）。
function onInspectIp(ip) {
  keywordDraft.value = ip
  onViewSwitch('flow')
  store.applyFilter({ keyword: ip })
}

// 文件名带本地时间戳：同一天导出多次不会互相覆盖（日期 key 同样禁用 toISOString）
function exportFilename() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  const day = `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}`
  return `用户日志_${day}_${p(d.getHours())}${p(d.getMinutes())}.csv`
}

async function onExport() {
  try {
    const res = await store.exportRows()
    if (!res) return // 已有导出在跑
    if (!res.items.length) {
      toast('当前筛选没有可导出的记录', 'info')
      return
    }
    const csv = buildOpCsv(res.items)
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url
    a.download = exportFilename()
    a.click()
    URL.revokeObjectURL(url)

    // 截断如实告知：悄悄少给几百条，比不导出更容易让人做出错误判断
    toast(
      res.truncated
        ? `已导出前 ${res.items.length} 条，其余 ${res.total - res.items.length} 条未导出`
        : `已导出 ${res.items.length} 条记录`,
      res.truncated ? 'warning' : 'success'
    )
  } catch (e) {
    toast(e.message || '导出失败', 'error')
  }
}

onMounted(() => {
  mm = gsap.matchMedia()
  mm.add('(prefers-reduced-motion: reduce)', () => {
    reduceMotion.value = true
    return () => {
      reduceMotion.value = false
    }
  })
  store.init()
})

onUnmounted(() => {
  mm?.revert()
  gsap.killTweensOf(bodyRef.value || [])
})

// watch 一律写在脚本末尾：注册时即求一次源值，写在依赖声明之前会触发 TDZ，
// 整个 setup 抛错导致页面白屏（eslint/build 都查不出）
let kwTimer = null
watch(keywordDraft, (v) => {
  if (kwTimer) clearTimeout(kwTimer)
  kwTimer = setTimeout(() => {
    kwTimer = null
    const kw = (v || '').trim()
    if (kw === store.filters.keyword) return
    store.applyFilter({ keyword: kw })
  }, 400)
})

// 两个列表各自的引用就是「新数据到了」的信号（loadCurrent 每次都整段替换数组）。
// pendingView 为空说明这次变动来自翻页或筛选，不播动画。
watch([() => store.sessions, () => store.logs], (next, prev) => {
  if (!pendingView) return
  if (next[0] === prev[0] && next[1] === prev[1]) return
  pendingView = ''
  nextTick(playBodyEnter)
})
</script>
