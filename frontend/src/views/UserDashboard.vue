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

    <!-- 筛选器：时间范围 / 打卡类型（普通用户无“指定用户”筛选，只看本人） -->
    <section class="dash-card p-4 fade-up flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div class="flex flex-wrap items-end gap-3">
        <label class="flex flex-col gap-1 text-xs font-medium text-ink-muted">
          时间范围
          <BaseSelect v-model="fRange" :options="[{ label: '近 7 天', value: '7d' }, { label: '近 30 天', value: '30d' }]" />
        </label>
        <label class="flex flex-col gap-1 text-xs font-medium text-ink-muted">
          打卡类型
          <BaseSelect v-model="fType" :options="[{ label: '全部类型', value: 'all' }, { label: '课程打卡', value: 'course' }, { label: '寝室打卡', value: 'dorm' }]" />
        </label>
      </div>
      <button class="rounded-lg border border-ink/15 px-3 py-1.5 text-sm font-medium text-ink-muted hover:bg-ink/5" @click="resetFilters">重置筛选</button>
    </section>

    <!-- ============ 我的汇总指标 ============ -->
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

    <!-- ============ 我的账号与打卡配置 ============ -->
    <section class="dash-card p-5 fade-up delay-2">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-semibold text-ink">我的账号与打卡配置</h3>
        <RouterLink to="/accounts" class="text-sm font-medium text-brand hover:underline">管理账号</RouterLink>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-ink-muted border-b border-ink/5">
              <th class="font-medium py-2.5 pr-4">账号</th>
              <th class="font-medium py-2.5 pr-4">类型</th>
              <th class="font-medium py-2.5 pr-4">打卡时段</th>
              <th class="font-medium py-2.5 pr-4 text-center">位置</th>
              <th class="font-medium py-2.5 pr-4 text-center">图片</th>
              <th class="font-medium py-2.5 pr-4">定时任务</th>
              <th class="font-medium py-2.5">最近结果</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in myAccounts" :key="a.account" class="border-b border-ink/5 last:border-0">
              <td class="py-3 pr-4 font-medium text-ink">{{ a.account }}</td>
              <td class="py-3 pr-4">
                <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium" :class="a.type === 'course' ? 'bg-brand/10 text-brand' : 'bg-info/10 text-info'">
                  {{ a.type === 'course' ? '课程打卡' : '寝室打卡' }}
                </span>
              </td>
              <td class="py-3 pr-4 text-ink-muted tabular-nums">{{ a.period }}</td>
              <td class="py-3 pr-4 text-center"><Icon :name="a.loc ? 'check' : 'close'" :size="16" :class="a.loc ? 'text-success' : 'text-ink/25'" /></td>
              <td class="py-3 pr-4 text-center"><Icon :name="a.img ? 'check' : 'close'" :size="16" :class="a.img ? 'text-success' : 'text-ink/25'" /></td>
              <td class="py-3 pr-4">
                <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium" :class="a.task ? 'bg-success/10 text-success' : 'bg-ink/5 text-ink-muted'">{{ a.task ? '运行中' : '已停止' }}</span>
              </td>
              <td class="py-3">
                <span class="inline-flex items-center gap-1.5 text-xs font-medium" :class="statusMeta[a.last].cls">
                  <span class="h-1.5 w-1.5 rounded-full" :class="dotCls(a.last)"></span>{{ statusMeta[a.last].label }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ============ 我的最近日志 ============ -->
    <section class="dash-card p-5 fade-up delay-3">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-semibold text-ink">我的最近打卡日志</h3>
        <RouterLink to="/sign-records" class="text-sm font-medium text-brand hover:underline">查看全部</RouterLink>
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

// ===== 当前角色（mock；真实由后端按 token 返回）=====
// [权限判断] role === '普通用户' 时渲染本页；管理员应由 DashboardView 分发到 AdminDashboard
const role = '普通用户'
const isAdmin = role === '管理员'

const statusMeta = {
  success: { label: '成功', cls: 'bg-success/10 text-success', dot: 'bg-success' },
  danger: { label: '失败', cls: 'bg-danger/10 text-danger', dot: 'bg-danger' },
  skip: { label: '跳过', cls: 'bg-amber/15 text-amber', dot: 'bg-amber' },
  muted: { label: '停用', cls: 'bg-ink/5 text-ink-muted', dot: 'bg-ink/30' }
}
const dotCls = (k) => statusMeta[k]?.dot || 'bg-ink/30'

// ===== 筛选器（普通用户：时间范围 + 类型）=====
const fRange = ref('7d')
const fType = ref('all')
function resetFilters() { fRange.value = '7d'; fType.value = 'all' }

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

// 我的账号与配置（mock）
// 预留后端请求：GET /api/me/accounts
const myAccounts = [
  { account: 'A-301', type: 'dorm', period: '每日 07:50', loc: true, img: true, task: true, last: 'success' },
  { account: 'A-302', type: 'dorm', period: '每日 07:50', loc: true, img: true, task: true, last: 'success' },
  { account: 'A-305', type: 'course', period: '每日 12:30', loc: true, img: false, task: true, last: 'skip' }
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
</script>
