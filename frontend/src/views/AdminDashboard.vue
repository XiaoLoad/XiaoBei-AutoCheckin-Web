<template>
  <div class="space-y-6">
    <!--
      ============================================================
      管理员仪表盘（A 平台 · 对接外部 B 打卡平台）
      [权限判断] 本页仅管理员可访问；路由守卫需校验 role === '管理员'，
      普通用户访问应重定向到 /dashboard 的普通用户视图。
      数据来源：全站汇总、全站图表、额度预警、调度器/队列均为
      管理员专属视角，普通用户只能看本人维度（见 UserDashboard.vue）。
      ============================================================
    -->

    <!-- 筛选器：指定用户 / 时间范围 / 打卡类型 -->
    <!-- [权限判断] 指定用户筛选为管理员专属；普通用户无此筛选项（只看本人） -->
    <section class="dash-card p-4 fade-up flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div class="flex flex-wrap items-end gap-3">
        <label class="flex flex-col gap-1 text-xs font-medium text-ink-muted">
          指定用户
          <select v-model="fUser" class="mt-0.5 rounded-lg border border-ink/15 bg-white px-3 py-1.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30">
            <option value="">全站用户</option>
            <option v-for="u in userOptions" :key="u" :value="u">{{ u }}</option>
          </select>
        </label>
        <label class="flex flex-col gap-1 text-xs font-medium text-ink-muted">
          时间范围
          <select v-model="fRange" class="mt-0.5 rounded-lg border border-ink/15 bg-white px-3 py-1.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30">
            <option value="7d">近 7 天</option>
            <option value="30d">近 30 天</option>
          </select>
        </label>
        <label class="flex flex-col gap-1 text-xs font-medium text-ink-muted">
          打卡类型
          <select v-model="fType" class="mt-0.5 rounded-lg border border-ink/15 bg-white px-3 py-1.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30">
            <option value="all">全部类型</option>
            <option value="course">课程打卡</option>
            <option value="dorm">寝室打卡</option>
          </select>
        </label>
      </div>
      <button class="rounded-lg border border-ink/15 px-3 py-1.5 text-sm font-medium text-ink-muted hover:bg-ink/5" @click="resetFilters">
        重置筛选
      </button>
    </section>

    <!-- ============ 全站汇总指标 ============ -->
    <!-- [权限判断] 全站汇总仅管理员可见 -->
    <section>
      <div class="flex items-center gap-2 mb-3">
        <span class="text-[11px] font-semibold tracking-wider text-ink-muted uppercase">全站汇总</span>
        <span class="h-px flex-1 bg-ink/10"></span>
        <span class="text-xs text-ink-muted">管理员视角</span>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label="总用户数" :value="summary.totalUsers" unit="人" icon="members" tone="brand" :delta="`活跃 ${summary.activeUsers} 人`" delta-type="flat" delta-hint="全站" :delay="1" />
        <StatCard label="全部 B 账号" :value="summary.totalAccounts" unit="个" icon="authorize" tone="info" :delta="`单平台 · ${summary.platformName}`" delta-type="flat" delta-hint="B 平台" :delay="2" />
        <StatCard
          label="额度占用" :value="quotaPct" unit="%"
          icon="tasks" :tone="quotaPct >= 90 ? 'danger' : 'amber'"
          :delta="`${summary.quotaUsed} / ${summary.quotaTotal}`" delta-type="flat" delta-hint="已用 / 上限" :delay="3"
        />
        <StatCard
          label="全站今日打卡" :value="summary.today.total" unit="次" icon="check" tone="success"
          :delta="`成功 ${summary.today.success} · 失败 ${summary.today.fail} · 跳过 ${summary.today.skip}`" delta-type="flat" delta-hint="今日累计" :delay="4"
        />
      </div>
    </section>

    <!-- ============ 图表区 ============ -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- 全站打卡趋势（7天/30天 切换） -->
      <section class="dash-card p-5 lg:col-span-2 fade-up delay-2">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="font-semibold text-ink">全站打卡趋势</h3>
            <p class="text-xs text-ink-muted mt-0.5">成功 / 失败 / 跳过 · 后台按配置定时执行结果</p>
          </div>
          <div class="flex rounded-lg border border-ink/15 p-0.5 text-xs">
            <button class="rounded-md px-2.5 py-1 font-medium" :class="fRange === '7d' ? 'bg-brand text-white' : 'text-ink-muted'" @click="fRange = '7d'">7 天</button>
            <button class="rounded-md px-2.5 py-1 font-medium" :class="fRange === '30d' ? 'bg-brand text-white' : 'text-ink-muted'" @click="fRange = '30d'">30 天</button>
          </div>
        </div>
        <BaseChart :option="trendOption" height="290px" />
      </section>

      <!-- 失败原因分布 -->
      <!-- [权限判断] 失败原因分布为全站视角，管理员专属 -->
      <section class="dash-card p-5 fade-up delay-3">
        <h3 class="font-semibold text-ink mb-1">失败原因分布</h3>
        <p class="text-xs text-ink-muted mb-2">近 30 天 · 共 {{ failTotal }} 次失败</p>
        <BaseChart :option="failReasonOption" height="290px" />
      </section>
    </div>

    <!-- 用户账号额度占用柱状图 -->
    <!-- [权限判断] 额度占用为管理员全局管理视角 -->
    <section class="dash-card p-5 fade-up delay-3">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h3 class="font-semibold text-ink">用户账号额度占用</h3>
          <p class="text-xs text-ink-muted mt-0.5">各用户已用 / 上限 · 占用率越高越需关注</p>
        </div>
      </div>
      <BaseChart :option="quotaOption" height="300px" />
    </section>

    <!-- ============ 列表模块 ============ -->
    <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <!-- 额度预警用户列表 -->
      <!-- [权限判断] 额度预警为管理员分配/管控视角 -->
      <section class="dash-card p-5 fade-up delay-4">
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-semibold text-ink">额度预警用户</h3>
          <span class="rounded-full bg-danger/10 px-2.5 py-0.5 text-xs font-medium text-danger">占用 ≥ 90%</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-ink-muted border-b border-ink/5">
                <th class="font-medium py-2.5 pr-4">用户</th>
                <th class="font-medium py-2.5 pr-4 text-right">已用 / 上限</th>
                <th class="font-medium py-2.5 pr-4">占用率</th>
                <th class="font-medium py-2.5">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in quotaWarnings" :key="u.name" class="border-b border-ink/5 last:border-0">
                <td class="py-3 pr-4 font-medium text-ink">{{ u.name }}</td>
                <td class="py-3 pr-4 text-right text-ink-muted tabular-nums">{{ u.used }} / {{ u.limit }}</td>
                <td class="py-3 pr-4">
                  <div class="flex items-center gap-2 min-w-[120px]">
                    <div class="h-1.5 flex-1 rounded-full bg-ink/10 overflow-hidden">
                      <div class="h-full rounded-full" :class="u.pct >= 100 ? 'bg-danger' : 'bg-amber'" :style="{ width: Math.min(u.pct, 100) + '%' }"></div>
                    </div>
                    <span class="text-xs tabular-nums" :class="u.pct >= 100 ? 'text-danger' : 'text-amber'">{{ u.pct }}%</span>
                  </div>
                </td>
                <td class="py-3">
                  <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium" :class="u.pct >= 100 ? 'bg-danger/10 text-danger' : 'bg-amber/15 text-amber'">
                    {{ u.pct >= 100 ? '已满额' : '预警' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 高频失败风险用户 -->
      <!-- [权限判断] 风险用户为全站质量监控视角 -->
      <section class="dash-card p-5 fade-up delay-4">
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-semibold text-ink">高频失败风险用户</h3>
          <span class="rounded-full bg-danger/10 px-2.5 py-0.5 text-xs font-medium text-danger">失败率 ≥ 10%</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-ink-muted border-b border-ink/5">
                <th class="font-medium py-2.5 pr-4">用户</th>
                <th class="font-medium py-2.5 pr-4 text-right">失败次数</th>
                <th class="font-medium py-2.5 pr-4 text-right">失败率</th>
                <th class="font-medium py-2.5">主要原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in riskUsers" :key="u.name" class="border-b border-ink/5 last:border-0">
                <td class="py-3 pr-4 font-medium text-ink">{{ u.name }}</td>
                <td class="py-3 pr-4 text-right text-ink-muted tabular-nums">{{ u.fails }}</td>
                <td class="py-3 pr-4 text-right font-medium text-danger tabular-nums">{{ u.rate }}%</td>
                <td class="py-3 text-ink-muted">{{ u.reason }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <!-- 全局最新打卡日志 -->
    <!-- [权限判断] 全站日志为管理员监控视角；普通用户仅见本人 -->
    <section class="dash-card p-5 fade-up delay-4">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-semibold text-ink">全局最新打卡日志</h3>
        <span class="text-xs text-ink-muted">按筛选条件（用户 / 类型）实时过滤</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-ink-muted border-b border-ink/5">
              <th class="font-medium py-2.5 pr-4">时间</th>
              <th class="font-medium py-2.5 pr-4">用户</th>
              <th class="font-medium py-2.5 pr-4">账号</th>
              <th class="font-medium py-2.5 pr-4">类型</th>
              <th class="font-medium py-2.5 pr-4">结果</th>
              <th class="font-medium py-2.5">说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in filteredLogs" :key="i" class="border-b border-ink/5 last:border-0">
              <td class="py-3 pr-4 text-ink-muted tabular-nums">{{ r.time }}</td>
              <td class="py-3 pr-4 font-medium text-ink">{{ r.user }}</td>
              <td class="py-3 pr-4 text-ink-muted">{{ r.account }}</td>
              <td class="py-3 pr-4">
                <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium" :class="r.type === 'course' ? 'bg-brand/10 text-brand' : 'bg-info/10 text-info'">
                  {{ r.type === 'course' ? '课程打卡' : '寝室打卡' }}
                </span>
              </td>
              <td class="py-3 pr-4">
                <span class="inline-flex items-center gap-1.5 text-xs font-medium" :class="statusMeta[r.result].cls">
                  <span class="h-1.5 w-1.5 rounded-full" :class="dotCls(r.result)"></span>
                  {{ statusMeta[r.result].label }}
                </span>
              </td>
              <td class="py-3 text-ink-muted">{{ r.note }}</td>
            </tr>
            <tr v-if="!filteredLogs.length"><td colspan="6" class="py-6 text-center text-ink-muted">当前筛选条件下无日志</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ============ 调度器运行状态 + 任务队列 ============ -->
    <!-- [权限判断] 调度器/队列为系统级运维视角，仅管理员 -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <section class="dash-card p-5 fade-up delay-5">
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-semibold text-ink">调度器运行状态</h3>
          <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium" :class="scheduler.running ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'">
            <span class="h-1.5 w-1.5 rounded-full" :class="scheduler.running ? 'bg-success animate-pulse' : 'bg-danger'"></span>
            {{ scheduler.running ? '运行中' : '已暂停' }}
          </span>
        </div>
        <dl class="space-y-2.5 text-sm">
          <div class="flex items-center justify-between"><dt class="text-ink-muted">调度模式</dt><dd class="font-medium text-ink">{{ scheduler.mode }}</dd></div>
          <div class="flex items-center justify-between"><dt class="text-ink-muted">下次执行</dt><dd class="font-medium text-ink tabular-nums">{{ scheduler.nextRun }}</dd></div>
          <div class="flex items-center justify-between"><dt class="text-ink-muted">心跳</dt><dd class="font-medium text-success">{{ scheduler.heartbeat }}</dd></div>
          <div class="flex items-center justify-between"><dt class="text-ink-muted">今日触发</dt><dd class="font-medium text-ink tabular-nums">{{ scheduler.triggeredToday }} 次</dd></div>
        </dl>
      </section>

      <section class="dash-card p-5 lg:col-span-2 fade-up delay-5">
        <h3 class="font-semibold text-ink mb-4">任务队列信息</h3>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div v-for="q in queueStats" :key="q.label" class="rounded-xl border border-ink/5 bg-ink/[0.02] p-3">
            <div class="text-2xl font-bold tabular-nums" :class="q.cls">{{ q.value }}</div>
            <div class="mt-1 text-xs text-ink-muted">{{ q.label }}</div>
          </div>
        </div>
        <p class="mt-3 text-xs text-ink-muted">队列由后端定时调度器维护，按用户配置时间触发打卡任务；失败任务进入重试队列。</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import StatCard from '@/components/StatCard.vue'
import BaseChart from '@/components/BaseChart.vue'
import Icon from '@/components/Icon.vue'

// ===== 当前角色（mock；真实由后端按 token 返回）=====
// [权限判断] role === '管理员' 时渲染本页；否则应由 DashboardView 分发到 UserDashboard
const role = '管理员'
const isAdmin = role === '管理员'

// ===== 状态映射 =====
const statusMeta = {
  success: { label: '成功', cls: 'bg-success/10 text-success', dot: 'bg-success' },
  danger: { label: '失败', cls: 'bg-danger/10 text-danger', dot: 'bg-danger' },
  skip: { label: '跳过', cls: 'bg-amber/15 text-amber', dot: 'bg-amber' }
}
const dotCls = (k) => statusMeta[k]?.dot || 'bg-ink/30'

// ===== 筛选器状态 =====
const fUser = ref('')
const fRange = ref('7d')
const fType = ref('all')
const userOptions = ['张明', '李雷', '王芳', '赵强', '陈静', '刘洋', '孙丽', '周杰']
function resetFilters() { fUser.value = ''; fRange.value = '7d'; fType.value = 'all' }

// ===== 全站汇总指标（mock）=====
// 预留后端请求：GET /api/admin/overview
//   axios.get('/api/admin/overview').then(r => summary.value = r.data)
const summary = {
  totalUsers: 248,
  activeUsers: 231,
  platformName: 'B 打卡平台',
  totalAccounts: 312,
  quotaUsed: 312,
  quotaTotal: 400,
  today: { success: 1842, fail: 73, skip: 226, total: 2141 }
}
const quotaPct = Math.round((summary.quotaUsed / summary.quotaTotal) * 100)

// ===== 趋势数据（mock，7天/30天）=====
// 预留后端请求：GET /api/admin/trend?range=7d|30d&type=course|dorm|all&user=xxx
const trend7 = [
  { d: '08-08', success: 1820, fail: 65, skip: 210 },
  { d: '08-09', success: 1905, fail: 58, skip: 198 },
  { d: '08-10', success: 1760, fail: 72, skip: 240 },
  { d: '08-11', success: 1888, fail: 61, skip: 205 },
  { d: '08-12', success: 1922, fail: 54, skip: 188 },
  { d: '08-13', success: 1810, fail: 80, skip: 230 },
  { d: '08-14', success: 1842, fail: 73, skip: 226 }
]
function genTrend30() {
  const arr = []
  for (let i = 29; i >= 0; i--) {
    const day = new Date(2026, 7, 14)
    day.setDate(day.getDate() - i)
    const dd = `${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`
    arr.push({ d: dd, success: 1800 + Math.round(Math.random() * 200), fail: 50 + Math.round(Math.random() * 40), skip: 180 + Math.round(Math.random() * 80) })
  }
  return arr
}
const trend30 = genTrend30()
const activeTrend = computed(() => (fRange.value === '30d' ? trend30 : trend7))

const cSuccess = '#16a34a', cDanger = '#dc2626', cSkip = '#F2A65A', cInk = '#5B6478', cGrid = 'rgba(20,33,61,0.06)', cBrand = '#1674f8'
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

// ===== 失败原因分布（mock）=====
// 预留后端请求：GET /api/admin/fail-reasons?range=30d
const failReasons = [
  { name: '登录失效 (401/403)', value: 34, color: '#dc2626' },
  { name: '接口超时', value: 21, color: '#F2A65A' },
  { name: '验证码识别失败', value: 12, color: '#1674f8' },
  { name: '网络异常', value: 8, color: '#8b5cf6' },
  { name: '其他', value: 5, color: '#5B6478' }
]
const failTotal = failReasons.reduce((s, r) => s + r.value, 0)
const failReasonOption = {
  tooltip: { trigger: 'item', backgroundColor: 'rgba(20,33,61,0.92)', borderWidth: 0, textStyle: { color: '#fff', fontSize: 12 }, formatter: '{b}：{c} 次 ({d}%)' },
  legend: { bottom: 0, textStyle: { color: cInk, fontSize: 11 }, type: 'scroll' },
  series: [{
    type: 'pie', radius: ['45%', '70%'], center: ['50%', '42%'], avoidLabelOverlap: true,
    label: { show: false }, itemStyle: { borderColor: '#fff', borderWidth: 2 },
    data: failReasons.map((r) => ({ value: r.value, name: r.name, itemStyle: { color: r.color } }))
  }]
}

// ===== 用户账号额度占用（mock，Top 10）=====
// 预留后端请求：GET /api/admin/quota-occupancy
const quotaUsers = [
  { name: '张明', used: 19, limit: 20 },
  { name: '陈静', used: 10, limit: 10 },
  { name: '李雷', used: 17, limit: 20 },
  { name: '王芳', used: 14, limit: 20 },
  { name: '赵强', used: 9, limit: 10 },
  { name: '刘洋', used: 8, limit: 10 },
  { name: '孙丽', used: 4, limit: 10 },
  { name: '周杰', used: 2, limit: 10 },
  { name: '吴敏', used: 18, limit: 20 },
  { name: '郑浩', used: 6, limit: 20 }
]
const quotaOption = {
  grid: { left: 60, right: 24, top: 24, bottom: 24 },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: 'rgba(20,33,61,0.92)', borderWidth: 0, textStyle: { color: '#fff', fontSize: 12 }, formatter: (p) => { const u = quotaUsers[p[0].dataIndex]; return `${u.name}<br/>已用 ${u.used} / 上限 ${u.limit}（${Math.round(u.used / u.limit * 100)}%）` } },
  legend: { top: 0, right: 0, textStyle: { color: cInk, fontSize: 12 } },
  xAxis: { type: 'value', axisLabel: { color: cInk, fontSize: 12 }, splitLine: { lineStyle: { color: cGrid, type: 'dashed' } } },
  yAxis: { type: 'category', data: quotaUsers.map((u) => u.name), axisLine: { lineStyle: { color: 'rgba(20,33,61,0.12)' } }, axisTick: { show: false }, axisLabel: { color: cInk, fontSize: 12 } },
  series: [
    { name: '已用', type: 'bar', stack: 'q', barWidth: 18, data: quotaUsers.map((u) => u.used), itemStyle: { color: cBrand, borderRadius: [3, 0, 0, 3] }, animationDuration: 1000 },
    { name: '剩余', type: 'bar', stack: 'q', barWidth: 18, data: quotaUsers.map((u) => u.limit - u.used), itemStyle: { color: 'rgba(20,33,61,0.08)', borderRadius: [0, 3, 3, 0] }, animationDuration: 1000 }
  ]
}

// ===== 额度预警用户（占用 ≥ 90%）=====
const quotaWarnings = computed(() => quotaUsers.map((u) => ({ ...u, pct: Math.round(u.used / u.limit * 100) })).filter((u) => u.pct >= 90).sort((a, b) => b.pct - a.pct))

// ===== 高频失败风险用户（mock）=====
// 预留后端请求：GET /api/admin/risk-users
const riskUsers = [
  { name: '李雷', fails: 42, rate: 18.4, reason: '登录失效 (401/403)' },
  { name: '王芳', fails: 28, rate: 12.1, reason: '接口超时' },
  { name: '赵强', fails: 19, rate: 11.3, reason: '验证码识别失败' },
  { name: '孙丽', fails: 15, rate: 10.6, reason: '网络异常' }
]

// ===== 全局最新打卡日志（mock）=====
// 预留后端请求：GET /api/admin/logs?user=&type=&range=
const allLogs = [
  { time: '15:02', user: '张明', account: 'A-301', type: 'dorm', result: 'success', note: '已自动完成打卡' },
  { time: '15:01', user: '李雷', account: 'B-105', type: 'course', result: 'danger', note: '接口返回 403，重试失败' },
  { time: '15:00', user: '王芳', account: 'C-201', type: 'dorm', result: 'success', note: '已自动完成打卡' },
  { time: '14:58', user: '陈静', account: 'E-501', type: 'course', result: 'skip', note: '当日无打卡任务，自动跳过' },
  { time: '14:55', user: '刘洋', account: 'F-601', type: 'dorm', result: 'success', note: '已自动完成打卡' },
  { time: '14:52', user: '赵强', account: 'D-401', type: 'course', result: 'danger', note: '验证码识别失败' },
  { time: '14:50', user: '吴敏', account: 'G-701', type: 'dorm', result: 'success', note: '已自动完成打卡' },
  { time: '14:48', user: '周杰', account: 'F-602', type: 'course', result: 'skip', note: '当日无打卡任务，自动跳过' },
  { time: '14:45', user: '郑浩', account: 'H-801', type: 'dorm', result: 'success', note: '已自动完成打卡' },
  { time: '14:42', user: '孙丽', account: 'I-901', type: 'course', result: 'danger', note: '网络异常，已入重试队列' }
]
const filteredLogs = computed(() =>
  allLogs.filter((r) =>
    (!fUser.value || r.user === fUser.value) &&
    (fType.value === 'all' || r.type === fType.value)
  )
)

// ===== 调度器状态 + 任务队列（mock）=====
// 预留后端请求：GET /api/admin/scheduler、GET /api/admin/queue
const scheduler = {
  running: true,
  mode: '固定间隔 · 每 5 分钟',
  nextRun: '2026-08-14 15:10',
  heartbeat: '正常 · 3 秒前',
  triggeredToday: 2141
}
const queueStats = [
  { label: '队列中任务', value: 5, cls: 'text-brand' },
  { label: '执行中', value: 2, cls: 'text-success' },
  { label: '待执行', value: 5, cls: 'text-info' },
  { label: '失败待重试', value: 1, cls: 'text-danger' }
]
</script>
