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
          label="我的额度占用" :value="quotaPct" unit="%"
          icon="tasks" :tone="quotaPct >= 90 ? 'danger' : 'amber'"
          :delta="`${me.quotaUsed} / ${me.quotaLimit}`" delta-type="flat" delta-hint="已用 / 上限" :delay="1"
        />
        <StatCard label="我的 B 账号" :value="me.accounts" unit="个" icon="authorize" tone="info" :delta="`单平台 · ${me.platform}`" delta-type="flat" delta-hint="B 平台" :delay="2" />
        <StatCard label="运行中定时任务" :value="me.activeTasks" unit="个" icon="clock" tone="success" :delta="`共 ${me.tasks} 个`" delta-type="flat" delta-hint="已启用" :delay="3" />
        <StatCard
          label="我的今日打卡" :value="me.today.total" unit="次" icon="check" tone="success"
          :delta="`成功 ${me.today.success} · 失败 ${me.today.fail} · 跳过 ${me.today.skip}`" delta-type="flat" delta-hint="今日累计" :delay="4"
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
      </section>

      <!-- 打卡类型分布 -->
      <section class="dash-card p-5 fade-up delay-3">
        <h3 class="font-semibold text-ink mb-1">打卡类型分布</h3>
        <p class="text-xs text-ink-muted mb-2">近 30 天 · 共 {{ typeTotal }} 次打卡</p>
        <BaseChart :option="typeDistOption" height="290px" />
      </section>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- 任务完成情况 -->
      <section class="dash-card p-5 fade-up delay-3">
        <h3 class="font-semibold text-ink mb-1">任务完成情况</h3>
        <p class="text-xs text-ink-muted mb-2">近 30 天 · 执行结果占比</p>
        <BaseChart :option="taskOption" height="260px" />
      </section>

      <!-- 我的账号状态速览（精简，替代原大表） -->
      <section class="dash-card p-5 lg:col-span-2 fade-up delay-4">
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-semibold text-ink">我的账号状态</h3>
          <RouterLink to="/accounts" class="text-sm font-medium text-brand hover:underline">管理账号</RouterLink>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div v-for="a in myAccounts" :key="a.account" class="rounded-xl border border-ink/5 bg-ink/[0.02] p-3.5">
            <div class="flex items-center justify-between gap-2">
              <span class="truncate font-medium text-ink">{{ a.account }}</span>
              <span class="inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-medium" :class="a.type === 'course' ? 'bg-brand/10 text-brand' : 'bg-info/10 text-info'">
                {{ a.type === 'course' ? '课程' : '寝室' }}
              </span>
            </div>
            <div class="mt-3 flex items-center gap-1.5 text-xs font-medium" :class="statusMeta[a.last].cls">
              <span class="h-1.5 w-1.5 rounded-full" :class="dotCls(a.last)"></span>{{ statusMeta[a.last].label }}
            </div>
            <p class="mt-1 text-xs text-ink-muted">{{ a.period }} 打卡</p>
          </div>
        </div>
      </section>
    </div>

    <!-- ============ 我的最近打卡日志 ============ -->
    <section class="dash-card p-5 fade-up delay-4">
      <div class="flex items-center justify-between gap-3 mb-4">
        <h3 class="font-semibold text-ink">我的最近打卡日志</h3>
        <div class="flex items-center gap-2 sm:gap-3">
          <div class="w-32 sm:w-36">
            <BaseSelect v-model="fType" size="sm" :options="[{ label: '全部类型', value: 'all' }, { label: '课程打卡', value: 'course' }, { label: '寝室打卡', value: 'dorm' }]" />
          </div>
          <RouterLink to="/sign-records" class="shrink-0 text-sm font-medium text-brand hover:underline">查看全部</RouterLink>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-ink-muted border-b border-ink/5">
              <th class="font-medium py-2.5 pr-4">时间</th>
              <th class="font-medium py-2.5 pr-4">账号</th>
              <th class="font-medium py-2.5 pr-4">类型</th>
              <th class="font-medium py-2.5 pr-4">结果</th>
              <th class="font-medium py-2.5">说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in filteredLogs" :key="i" class="border-b border-ink/5 last:border-0">
              <td class="py-3 pr-4 text-ink-muted tabular-nums">{{ r.time }}</td>
              <td class="py-3 pr-4 font-medium text-ink">{{ r.account }}</td>
              <td class="py-3 pr-4">
                <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium" :class="r.type === 'course' ? 'bg-brand/10 text-brand' : 'bg-info/10 text-info'">
                  {{ r.type === 'course' ? '课程打卡' : '寝室打卡' }}
                </span>
              </td>
              <td class="py-3 pr-4">
                <span class="inline-flex items-center gap-1.5 text-xs font-medium" :class="statusMeta[r.result].cls">
                  <span class="h-1.5 w-1.5 rounded-full" :class="dotCls(r.result)"></span>{{ statusMeta[r.result].label }}
                </span>
              </td>
              <td class="py-3 text-ink-muted">{{ r.note }}</td>
            </tr>
            <tr v-if="!filteredLogs.length"><td colspan="5" class="py-6 text-center text-ink-muted">当前筛选条件下无日志</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { RouterLink } from 'vue-router'
import StatCard from '@/components/StatCard.vue'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import BaseChart from '@/components/BaseChart.vue'

// ===== 当前角色（mock；真实由后端按 token 返回）=====
// [权限判断] role === '普通用户' 时渲染本页；管理员应由 DashboardView 分发到 AdminDashboard
const role = '普通用户'

// ===== 状态映射 =====
const statusMeta = {
  success: { label: '成功', cls: 'bg-success/10 text-success', dot: 'bg-success' },
  danger: { label: '失败', cls: 'bg-danger/10 text-danger', dot: 'bg-danger' },
  skip: { label: '跳过', cls: 'bg-amber/15 text-amber', dot: 'bg-amber' },
  muted: { label: '停用', cls: 'bg-ink/5 text-ink-muted', dot: 'bg-ink/30' }
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

// ===== 筛选状态（普通用户：时间范围由趋势图切换控制，类型筛选最近日志）=====
const fRange = ref('7d')
const fType = ref('all')

// ===== 我的数据（mock）=====
// 预留后端请求：GET /api/me/overview
const me = {
  quotaUsed: 3,
  quotaLimit: 20, // 管理员分配的额度上限
  platform: 'B 打卡平台',
  accounts: 3,
  tasks: 3,
  activeTasks: 3,
  today: { success: 6, fail: 0, skip: 1, total: 7 }
}
const quotaPct = Math.round((me.quotaUsed / me.quotaLimit) * 100)

// 我的账号状态（mock，精简展示）
// 预留后端请求：GET /api/me/accounts
const myAccounts = [
  { account: 'A-301', type: 'dorm', period: '每日 07:50', last: 'success' },
  { account: 'A-302', type: 'dorm', period: '每日 07:50', last: 'success' },
  { account: 'A-305', type: 'course', period: '每日 12:30', last: 'skip' }
]

// 我的最近日志（mock）
// 预留后端请求：GET /api/me/logs?range=7d|30d&type=course|dorm|all
const myLogs = [
  { time: '07:52', account: 'A-301', type: 'dorm', result: 'success', note: '已自动完成打卡' },
  { time: '07:51', account: 'A-302', type: 'dorm', result: 'success', note: '已自动完成打卡' },
  { time: '12:31', account: 'A-305', type: 'course', result: 'skip', note: '当日无打卡任务，自动跳过' },
  { time: '昨天 07:50', account: 'A-301', type: 'dorm', result: 'success', note: '已自动完成打卡' },
  { time: '昨天 12:30', account: 'A-305', type: 'course', result: 'success', note: '已自动完成打卡' },
  { time: '前天 07:50', account: 'A-302', type: 'dorm', result: 'success', note: '已自动完成打卡' },
  { time: '前天 07:49', account: 'A-301', type: 'dorm', result: 'danger', note: '接口返回 403，重试失败' }
]
const filteredLogs = computed(() => myLogs.filter((r) => fType.value === 'all' || r.type === fType.value))

// ===== 图表配色（与 AdminDashboard 保持一致）=====
const cSuccess = '#16a34a', cDanger = '#dc2626', cSkip = '#F2A65A', cInk = '#5B6478', cGrid = 'rgba(20,33,61,0.06)', cBrand = '#1674f8', cInfo = '#0ea5e9'

// ===== 我的签到趋势（mock，7天/30天，个人级数值）=====
// 预留后端请求：GET /api/me/trend?range=7d|30d&type=course|dorm|all
const trend7 = [
  { d: '08-17', success: 2, fail: 0, skip: 1 },
  { d: '08-18', success: 3, fail: 0, skip: 0 },
  { d: '08-19', success: 2, fail: 1, skip: 0 },
  { d: '08-20', success: 3, fail: 0, skip: 0 },
  { d: '08-21', success: 2, fail: 0, skip: 1 },
  { d: '08-22', success: 3, fail: 0, skip: 0 },
  { d: '08-23', success: 2, fail: 0, skip: 1 }
]
function genTrend30() {
  const arr = []
  for (let i = 29; i >= 0; i--) {
    const day = new Date(2026, 7, 23)
    day.setDate(day.getDate() - i)
    const dd = `${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`
    arr.push({ d: dd, success: 2 + Math.round(Math.random() * 2), fail: Math.round(Math.random()), skip: Math.round(Math.random()) })
  }
  return arr
}
const trend30 = genTrend30()
const activeTrend = computed(() => (fRange.value === '30d' ? trend30 : trend7))

const trendOption = computed(() => ({
  grid: { left: 40, right: 16, top: 40, bottom: 28 },
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(20,33,61,0.92)', borderWidth: 0, padding: [6, 10],
    textStyle: { color: '#fff', fontSize: 12 },
    axisPointer: { type: 'line', lineStyle: { color: cBrand, type: 'dashed' } }
  },
  legend: { top: 0, right: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: cInk, fontSize: 12 } },
  xAxis: {
    type: 'category', boundaryGap: false, data: activeTrend.value.map((p) => p.d),
    axisLine: { lineStyle: { color: 'rgba(20,33,61,0.12)' } }, axisTick: { show: false },
    axisLabel: { color: cInk, fontSize: 12, interval: fRange.value === '30d' ? 4 : 0 }
  },
  yAxis: { type: 'value', min: 0, axisLabel: { color: cInk, fontSize: 12 }, splitLine: { lineStyle: { color: cGrid, type: 'dashed' } } },
  series: [
    { name: '成功', type: 'line', smooth: true, symbol: 'circle', symbolSize: 6, data: activeTrend.value.map((p) => p.success), lineStyle: { width: 2.5, color: cSuccess }, itemStyle: { color: cSuccess }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(22,163,74,0.22)' }, { offset: 1, color: 'rgba(22,163,74,0.02)' }] } }, animationDuration: 1100, animationEasing: 'cubicOut' },
    { name: '失败', type: 'line', smooth: true, symbol: 'circle', symbolSize: 6, data: activeTrend.value.map((p) => p.fail), lineStyle: { width: 2.5, color: cDanger }, itemStyle: { color: cDanger }, animationDuration: 1100, animationEasing: 'cubicOut' },
    { name: '跳过', type: 'line', smooth: true, symbol: 'circle', symbolSize: 6, data: activeTrend.value.map((p) => p.skip), lineStyle: { width: 2.5, color: cSkip }, itemStyle: { color: cSkip }, animationDuration: 1100, animationEasing: 'cubicOut' }
  ]
}))

// ===== 打卡类型分布（mock，近30天）=====
// 预留后端请求：GET /api/me/type-dist
const typeDist = { course: 42, dorm: 48 }
const typeTotal = typeDist.course + typeDist.dorm
const typeDistOption = {
  tooltip: { trigger: 'item', backgroundColor: 'rgba(20,33,61,0.92)', borderWidth: 0, textStyle: { color: '#fff', fontSize: 12 }, formatter: '{b}：{c} 次 ({d}%)' },
  legend: { bottom: 0, textStyle: { color: cInk, fontSize: 11 }, type: 'scroll' },
  series: [{
    type: 'pie', radius: ['45%', '70%'], center: ['50%', '42%'], avoidLabelOverlap: true,
    label: { show: false }, itemStyle: { borderColor: '#fff', borderWidth: 2 },
    data: [
      { value: typeDist.course, name: '课程打卡', itemStyle: { color: cBrand } },
      { value: typeDist.dorm, name: '寝室打卡', itemStyle: { color: cInfo } }
    ]
  }]
}

// ===== 任务完成情况（mock，近30天）=====
// 预留后端请求：GET /api/me/task-summary
const taskSummary = { success: 138, fail: 9, skip: 23, pending: 6 }
const successRate = Math.round((taskSummary.success / (taskSummary.success + taskSummary.fail)) * 100)
const taskOption = {
  tooltip: { trigger: 'item', backgroundColor: 'rgba(20,33,61,0.92)', borderWidth: 0, textStyle: { color: '#fff', fontSize: 12 }, formatter: '{b}：{c} 次 ({d}%)' },
  title: {
    text: successRate + '%', subtext: '成功率',
    left: 'center', top: '38%',
    textStyle: { fontSize: 24, fontWeight: 'bold', color: cSuccess },
    subtextStyle: { fontSize: 11, color: cInk }
  },
  legend: { bottom: 0, textStyle: { color: cInk, fontSize: 11 }, type: 'scroll' },
  series: [{
    type: 'pie', radius: ['56%', '76%'], center: ['50%', '44%'], avoidLabelOverlap: true,
    label: { show: false }, itemStyle: { borderColor: '#fff', borderWidth: 2 },
    data: [
      { value: taskSummary.success, name: '成功', itemStyle: { color: cSuccess } },
      { value: taskSummary.fail, name: '失败', itemStyle: { color: cDanger } },
      { value: taskSummary.skip, name: '跳过', itemStyle: { color: cSkip } },
      { value: taskSummary.pending, name: '待执行', itemStyle: { color: cInk } }
    ]
  }]
}
</script>
