<template>
  <div class="space-y-6">
    <!--
      ============================================================
      普通用户仪表盘（A 平台 · 对接外部 B 打卡平台）
      [权限判断] 本页为普通用户视角：仅展示当前登录用户本人数据。
      账号数量受管理员分配的额度上限约束（quotaUsed / quotaLimit）。
      普通用户不可见：全站汇总、其他用户数据、额度预警、调度器/队列等管理员功能。
      ============================================================
    -->

    <!-- ============ 核心功能入口 ============ -->
    <section>
      <div class="flex items-center gap-2 mb-3">
        <span class="text-[11px] font-semibold tracking-wider text-ink-muted uppercase">核心功能</span>
        <span class="h-px flex-1 bg-ink/10"></span>
        <span class="text-xs text-ink-muted">快速进入常用模块</span>
      </div>
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <RouterLink
          v-for="q in quickActions"
          :key="q.to"
          :to="q.to"
          class="dash-card group flex items-center gap-3 p-4 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-ink/10"
        >
          <span class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand/10 text-brand transition group-hover:bg-brand group-hover:text-white">
            <Icon :name="q.icon" :size="20" />
          </span>
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold text-ink">{{ q.title }}</p>
            <p class="truncate text-xs text-ink-muted">{{ q.desc }}</p>
          </div>
        </RouterLink>
      </div>
    </section>

    <!-- ============ 我的状态概览 ============ -->
    <section>
      <div class="flex items-center gap-2 mb-3">
        <span class="text-[11px] font-semibold tracking-wider text-ink-muted uppercase">我的概览</span>
        <span class="h-px flex-1 bg-ink/10"></span>
        <span class="text-xs text-ink-muted">普通用户视角</span>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="我的额度占用" :value="me.quota.pct" unit="%"
          icon="tasks" :tone="me.quota.pct >= 90 ? 'danger' : 'amber'"
          :delta="`${me.quota.used} / ${me.quota.limit}`" delta-type="flat" delta-hint="已用 / 上限" :loading="loading"
        />
        <StatCard label="我的 B 账号" :value="me.accounts.total" unit="个" icon="authorize" tone="info" :delta="`单平台 · B 打卡平台`" delta-type="flat" delta-hint="B 平台" :loading="loading" />
        <StatCard label="运行中定时任务" :value="me.tasks.active" unit="个" icon="clock" tone="success" :delta="`共 ${me.tasks.total} 个`" delta-type="flat" delta-hint="已启用" :loading="loading" />
        <StatCard
          label="我的今日打卡" :value="me.today.total" unit="次" icon="check" tone="success"
          :delta="`成功 ${me.today.success} · 失败 ${me.today.fail} · 跳过 ${me.today.skip}`" delta-type="flat" delta-hint="今日累计" :loading="loading"
        />
      </div>
    </section>

    <!-- ============ 可视化图表区 ============ -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- 我的签到趋势（7天/30天 切换） -->
      <section class="dash-card p-5 lg:col-span-2 fade-up delay-2">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="font-semibold text-ink">我的签到趋势</h3>
            <p class="text-xs text-ink-muted mt-0.5">成功 / 失败 / 跳过 · 本人打卡执行情况</p>
          </div>
          <div class="flex rounded-lg border border-ink/15 p-0.5 text-xs">
            <button class="rounded-md px-2.5 py-1 font-medium" :class="fRange === '7d' ? 'bg-brand text-white' : 'text-ink-muted'" @click="fRange = '7d'">7 天</button>
            <button class="rounded-md px-2.5 py-1 font-medium" :class="fRange === '30d' ? 'bg-brand text-white' : 'text-ink-muted'" @click="fRange = '30d'">30 天</button>
          </div>
        </div>
        <BaseChart :option="trendOption" height="290px" />
        <p v-if="!loading && activeTrend.length === 0" class="mt-2 text-center text-xs text-ink-muted">近 {{ fRange === '30d' ? 30 : 7 }} 天暂无打卡数据</p>
      </section>

      <!-- 打卡类型分布 -->
      <section class="dash-card p-5 fade-up delay-3">
        <h3 class="font-semibold text-ink mb-1">打卡类型分布</h3>
        <p class="text-xs text-ink-muted mb-2">近 30 天 · 共 {{ typeTotal }} 次打卡</p>
        <BaseChart :option="typeDistOption" height="290px" />
        <p v-if="!loading && typeTotal === 0" class="mt-2 text-center text-xs text-ink-muted">近 30 天暂无打卡数据</p>
      </section>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- 任务完成情况 -->
      <section class="dash-card p-5 fade-up delay-3">
        <h3 class="font-semibold text-ink mb-1">任务完成情况</h3>
        <p class="text-xs text-ink-muted mb-2">近 30 天 · 执行结果占比</p>
        <BaseChart :option="taskOption" height="260px" />
        <p v-if="!loading && taskSummaryTotal === 0" class="mt-2 text-center text-xs text-ink-muted">近 30 天暂无执行记录</p>
      </section>

      <!-- 我的账号状态（仅显示已启用并配置好配置套的账号） -->
      <section class="dash-card p-5 lg:col-span-2 fade-up delay-4">
        <div class="flex items-center justify-between mb-4">
          <div class="min-w-0">
            <h3 class="font-semibold text-ink">我的账号状态</h3>
            <p class="text-xs text-ink-muted mt-0.5">已启用并配置 · 共 {{ me.accounts.items.length }} 个</p>
          </div>
          <RouterLink to="/schedules" class="shrink-0 text-sm font-medium text-brand hover:underline">定时任务</RouterLink>
        </div>
        <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <div v-for="i in 3" :key="i" class="h-[112px] rounded-xl border border-ink/5 bg-ink/5 animate-pulse" />
        </div>
        <div v-else-if="me.accounts.items.length === 0" class="py-8 text-center">
          <p class="text-sm text-ink-muted">还没有已启用并配置好配置套的账号</p>
          <RouterLink to="/sign-config" class="mt-2 inline-block text-sm font-medium text-brand hover:underline">去签到配置启用</RouterLink>
        </div>
        <template v-else>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <div v-for="a in visibleAccounts" :key="a.id"
                 class="group flex flex-col rounded-xl border border-ink/5 bg-ink/[0.02] p-4 transition hover:-translate-y-0.5 hover:border-brand/20 hover:shadow-md hover:shadow-ink/5">
              <div class="flex items-start gap-3">
                <span class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand/10 text-sm font-semibold text-brand">
                  {{ initialOf(a) }}
                </span>
                <div class="min-w-0 flex-1">
                  <p class="truncate font-semibold text-ink" :title="a.name || a.account">{{ a.name || a.account }}</p>
                  <p class="truncate text-xs text-ink-muted" :title="[a.college, a.major].filter(Boolean).join(' · ')">{{ [a.college, a.major].filter(Boolean).join(' · ') || '—' }}</p>
                </div>
                <span class="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium" :class="typeBadge(a.type)">{{ a.type }}</span>
              </div>
              <p class="mt-3 truncate text-xs text-ink-muted" :title="a.className">班级：{{ a.className || '—' }}</p>
              <div class="mt-auto flex items-center justify-between gap-2 pt-3">
                <span class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium" :class="statusMeta[a.lastStatus].cls">
                  <span class="h-1.5 w-1.5 rounded-full" :class="dotCls(a.lastStatus)"></span>{{ statusMeta[a.lastStatus].label }}
                </span>
                <span class="truncate text-[11px] text-ink-muted">{{ a.lastSignIn || '尚未打卡' }}</span>
              </div>
            </div>
          </div>
          <button v-if="me.accounts.items.length > ACCOUNT_LIMIT" @click="accountsExpanded = !accountsExpanded"
                  class="mt-3 mx-auto flex items-center gap-1 text-sm font-medium text-brand hover:underline">
            {{ accountsExpanded ? '收起' : `展开全部 ${me.accounts.items.length} 个账号` }}
            <Icon :name="accountsExpanded ? 'chevron-up' : 'chevron-down'" :size="14" />
          </button>
        </template>
      </section>
    </div>

    <!-- ============ 我的最近签到日志 ============ -->
    <section class="dash-card p-5 fade-up delay-4">
      <div class="flex items-center justify-between gap-3 mb-4">
        <h3 class="font-semibold text-ink">我的最近签到日志</h3>
        <div class="flex items-center gap-2 sm:gap-3">
          <div class="w-32 sm:w-36">
            <BaseSelect v-model="fType" size="sm" :options="[{ label: '全部类型', value: 'all' }, { label: '活动签到', value: 'activity' }, { label: '寝室打卡', value: 'dorm' }]" />
          </div>
          <RouterLink to="/task-logs" class="shrink-0 text-sm font-medium text-brand hover:underline">查看全部</RouterLink>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-ink-muted border-b border-ink/5">
              <th class="font-medium py-2.5 pr-4 whitespace-nowrap">时间</th>
              <th class="font-medium py-2.5 pr-4 whitespace-nowrap">姓名</th>
              <th class="font-medium py-2.5 pr-4 whitespace-nowrap">账号</th>
              <th class="font-medium py-2.5 pr-4 whitespace-nowrap">学院</th>
              <th class="font-medium py-2.5 pr-4 whitespace-nowrap">班级</th>
              <th class="font-medium py-2.5 pr-4 whitespace-nowrap">类型</th>
              <th class="font-medium py-2.5 pr-4 whitespace-nowrap">结果</th>
              <th class="font-medium py-2.5 whitespace-nowrap">说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in filteredLogs" :key="r.id || i" class="border-b border-ink/5 last:border-0 hover:bg-ink/[0.02]">
              <td class="py-3 pr-4 text-ink-muted tabular-nums whitespace-nowrap">{{ r.time }}</td>
              <td class="py-3 pr-4 font-medium text-ink whitespace-nowrap">{{ r.name || '—' }}</td>
              <td class="py-3 pr-4 text-ink-soft whitespace-nowrap">{{ r.account || '—' }}</td>
              <td class="py-3 pr-4 text-ink-muted whitespace-nowrap">{{ r.college || '—' }}</td>
              <td class="py-3 pr-4 text-ink-muted whitespace-nowrap">{{ r.className || '—' }}</td>
              <td class="py-3 pr-4">
                <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium" :class="r.type.includes('活动') ? 'bg-brand/10 text-brand' : 'bg-info/10 text-info'">
                  {{ r.type }}
                </span>
              </td>
              <td class="py-3 pr-4">
                <span class="inline-flex items-center gap-1.5 text-xs font-medium" :class="statusMeta[r.result].cls">
                  <span class="h-1.5 w-1.5 rounded-full" :class="dotCls(r.result)"></span>{{ statusMeta[r.result].label }}
                </span>
              </td>
              <td class="py-3 max-w-[260px]">
                <RouterLink
                  v-if="r.result === 'fail'"
                  :to="{ path: '/task-logs', query: { type: r.type.includes('活动') ? 'activity' : 'dorm', status: 'fail' } }"
                  class="inline-flex items-center gap-1 text-xs font-medium text-danger hover:underline"
                >
                  签到失败 · 查看详情
                  <Icon name="chevron-right" :size="12" />
                </RouterLink>
                <span v-else class="block truncate text-ink-muted" :title="r.note">{{ r.note || '—' }}</span>
              </td>
            </tr>
            <tr v-if="!loading && filteredLogs.length === 0"><td colspan="8" class="py-6 text-center text-ink-muted">暂无签到日志</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { storeToRefs } from 'pinia'
import StatCard from '@/components/StatCard.vue'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import BaseChart from '@/components/BaseChart.vue'
import { useDashboardStore } from '@/stores/dashboard'

const store = useDashboardStore()
const { overview: me, loading } = storeToRefs(store)

// ===== 状态映射 =====
const statusMeta = {
  success: { label: '成功', cls: 'bg-success/10 text-success', dot: 'bg-success' },
  fail: { label: '失败', cls: 'bg-danger/10 text-danger', dot: 'bg-danger' },
  skip: { label: '跳过', cls: 'bg-amber/15 text-amber', dot: 'bg-amber' },
  never: { label: '未打卡', cls: 'bg-ink/5 text-ink-muted', dot: 'bg-ink/30' },
  danger: { label: '失败', cls: 'bg-danger/10 text-danger', dot: 'bg-danger' }
}
const dotCls = (k) => statusMeta[k]?.dot || 'bg-ink/30'

// ===== 核心功能入口 =====
const quickActions = [
  { to: '/sign-config', icon: 'sliders', title: '签到配置', desc: '配置打卡参数与任务' },
  { to: '/accounts', icon: 'authorize', title: '账号管理', desc: '管理 B 平台账号' },
  { to: '/schedules', icon: 'clock', title: '定时任务', desc: '查看运行中的任务' },
  { to: '/sign-records', icon: 'calendar', title: '签到记录', desc: '查看历史打卡' },
  { to: '/settings', icon: 'settings', title: '系统设置', desc: '偏好与个性化' }
]

// ===== 筛选状态 =====
const fRange = ref('7d')
const fType = ref('all')

// ===== 派生：趋势 / 分布 / 完成情况 =====
const activeTrend = computed(() => me.value.trend?.[fRange.value] || [])
const typeTotal = computed(() => (me.value.typeDist?.dorm || 0) + (me.value.typeDist?.activity || 0))
const taskSummaryTotal = computed(
  () => (me.value.taskSummary?.success || 0) + (me.value.taskSummary?.fail || 0) + (me.value.taskSummary?.skip || 0)
)
const successRate = computed(() => {
  const s = me.value.taskSummary?.success || 0
  const f = me.value.taskSummary?.fail || 0
  return s + f > 0 ? Math.round((s / (s + f)) * 100) : 0
})

const filteredLogs = computed(() =>
  (me.value.recentLogs || []).filter((r) => {
    if (fType.value === 'all') return true
    const isActivity = r.type.includes('活动')
    return (isActivity ? 'activity' : 'dorm') === fType.value
  })
)

// ===== 账号卡片：默认只展示前 N 个，超出可展开（避免拉伸/显示不全）=====
const ACCOUNT_LIMIT = 6
const accountsExpanded = ref(false)
const visibleAccounts = computed(() => {
  const items = me.value.accounts.items || []
  return accountsExpanded.value ? items : items.slice(0, ACCOUNT_LIMIT)
})
// 账号类型徽标配色：与饼图一致（活动=品牌蓝 / 寝室=信息蓝 / 通用=中性）
const typeBadge = (t) => ({
  '通用': 'bg-ink/10 text-ink-soft',
  '寝室': 'bg-info/10 text-info',
  '活动': 'bg-brand/10 text-brand',
  '未配置': 'bg-ink/5 text-ink-muted',
}[t] || 'bg-ink/5 text-ink-muted')
// 头像首字：优先姓名，缺失回退登录账号
const initialOf = (a) => (a.name || a.account || '?').charAt(0)

// ===== 图表配色（与 App 设计令牌对齐：brand/success/danger/info/amber/ink）=====
const C = {
  success: '#16a34a',
  fail:    '#dc2626',
  skip:    '#F2A65A',
  brand:   '#1674f8',
  dorm:    '#0ea5e9',
  ink:     '#5B6478',
  grid:    'rgba(91,100,120,0.10)',
}
// hex + alpha → rgba 字符串（用于渐变面积）
const rgba = (hex, a) => {
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`
}
// 折线面积渐变（顶部稍浓、底部透明）
const areaFill = (hex) => ({
  type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
  colorStops: [{ offset: 0, color: rgba(hex, 0.22) }, { offset: 1, color: rgba(hex, 0.02) }],
})
// 单条趋势线：圆润曲线 + 白色描边端点 + 柔和渐变 + hover 聚焦其余淡出
function lineSeries(name, data, color) {
  return {
    name, type: 'line', smooth: true, symbol: 'circle', symbolSize: 7, showSymbol: true, data,
    lineStyle: { width: 2.5, color },
    itemStyle: { color, borderColor: '#fff', borderWidth: 2 },
    areaStyle: areaFill(color),
    emphasis: { focus: 'series' },
    animationDuration: 1100, animationEasing: 'cubicOut',
  }
}

const trendOption = computed(() => ({
  grid: { left: 44, right: 18, top: 40, bottom: 28 },
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(20,33,61,0.92)', borderWidth: 0, padding: [6, 10],
    textStyle: { color: '#fff', fontSize: 12 },
    axisPointer: { type: 'line', lineStyle: { color: C.brand, type: 'dashed' } }
  },
  legend: { top: 0, right: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: C.ink, fontSize: 12 } },
  xAxis: {
    type: 'category', boundaryGap: false, data: activeTrend.value.map((p) => p.date),
    axisLine: { lineStyle: { color: 'rgba(20,33,61,0.12)' } }, axisTick: { show: false },
    axisLabel: { color: C.ink, fontSize: 12, interval: fRange.value === '30d' ? 4 : 0 }
  },
  yAxis: { type: 'value', min: 0, axisLabel: { color: C.ink, fontSize: 12 }, splitLine: { lineStyle: { color: C.grid, type: 'dashed' } } },
  series: [
    lineSeries('成功', activeTrend.value.map((p) => p.success), C.success),
    lineSeries('失败', activeTrend.value.map((p) => p.fail), C.fail),
    lineSeries('跳过', activeTrend.value.map((p) => p.skip), C.skip),
  ]
}))

const typeDistOption = computed(() => ({
  tooltip: { trigger: 'item', backgroundColor: 'rgba(20,33,61,0.92)', borderWidth: 0, textStyle: { color: '#fff', fontSize: 12 }, formatter: '{b}：{c} 次 ({d}%)' },
  legend: { bottom: 0, textStyle: { color: C.ink, fontSize: 11 }, type: 'scroll' },
  series: [{
    type: 'pie', radius: ['46%', '70%'], center: ['50%', '42%'], avoidLabelOverlap: true,
    label: { show: false },
    itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 6 },
    emphasis: { scale: true, scaleSize: 6 },
    data: [
      { value: me.value.typeDist?.activity || 0, name: '活动打卡', itemStyle: { color: C.brand } },
      { value: me.value.typeDist?.dorm || 0, name: '寝室打卡', itemStyle: { color: C.dorm } }
    ]
  }]
}))

const taskOption = computed(() => ({
  tooltip: { trigger: 'item', backgroundColor: 'rgba(20,33,61,0.92)', borderWidth: 0, textStyle: { color: '#fff', fontSize: 12 }, formatter: '{b}：{c} 次 ({d}%)' },
  title: {
    text: successRate.value + '%', subtext: '成功率',
    left: 'center', top: '37%',
    textStyle: { fontSize: 24, fontWeight: 'bold', color: C.success },
    subtextStyle: { fontSize: 11, color: C.ink }
  },
  legend: { bottom: 0, textStyle: { color: C.ink, fontSize: 11 }, type: 'scroll' },
  series: [{
    type: 'pie', radius: ['56%', '76%'], center: ['50%', '44%'], avoidLabelOverlap: true,
    label: { show: false },
    itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 6 },
    emphasis: { scale: true, scaleSize: 6 },
    data: [
      { value: me.value.taskSummary?.success || 0, name: '成功', itemStyle: { color: C.success } },
      { value: me.value.taskSummary?.fail || 0, name: '失败', itemStyle: { color: C.fail } },
      { value: me.value.taskSummary?.skip || 0, name: '跳过', itemStyle: { color: C.skip } }
    ]
  }]
}))

onMounted(() => {
  store.loadOverview()
})
</script>
