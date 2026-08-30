<template>
  <div class="space-y-6">
    <!--
      ============================================================
      管理员仪表盘（A 平台 · 对接外部 B 打卡平台）
      [权限判断] 本页仅管理员可访问；数据全部来自 /api/admin/overview
      真实聚合端点（用户/账号/签到记录/调度器），无 mock。
      多用户策略：仪表盘只呈现「聚合 + Top-N + 阈值分桶」，
      全量明细归属用户管理页。
      ============================================================
    -->
    <RefreshStrip v-if="refreshing" />

    <!-- 首次加载骨架（此后切页回来为静默换新，不再闪骨架） -->
    <div v-if="loading && !loaded" class="space-y-6" aria-label="加载中">
      <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="h-[118px] rounded-2xl dash-card animate-pulse" />
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="h-[360px] rounded-2xl dash-card animate-pulse lg:col-span-2" />
        <div class="h-[360px] rounded-2xl dash-card animate-pulse" />
      </div>
      <div class="h-[280px] rounded-2xl dash-card animate-pulse" />
    </div>

    <template v-else>
      <!-- ============ 全站汇总指标 ============ -->
      <section>
        <div class="flex items-center gap-2 mb-3">
          <span class="text-[11px] font-semibold tracking-wider text-ink-muted uppercase">全站汇总</span>
          <span class="h-px flex-1 bg-ink/10"></span>
          <span class="text-xs text-ink-muted">管理员视角</span>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <StatCard label="总用户数" :value="summary.users" unit="人" icon="members" tone="brand"
                    :delta="`近30天活跃 ${summary.activeUsers30d} 人`" delta-type="flat" delta-hint="全站" :delay="1" count-up />
          <StatCard label="全部 B 账号" :value="summary.accounts" unit="个" icon="authorize" tone="info"
                    :delta="`启用中 ${summary.accountsEnabled} 个`" delta-type="flat" delta-hint="B 平台" :delay="2" count-up />
          <StatCard
            label="额度占用" :value="summary.quota.pct" unit="%"
            icon="tasks" :tone="summary.quota.pct >= 90 ? 'danger' : 'amber'"
            :delta="`${summary.quota.used} / ${summary.quota.total}`" delta-type="flat" delta-hint="已用 / 上限" :delay="3" count-up
          />
          <StatCard
            label="全站今日打卡" :value="summary.today.total" unit="次" icon="check" tone="success"
            :delta="`成功 ${summary.today.success} · 失败 ${summary.today.fail} · 跳过 ${summary.today.skip}`"
            delta-type="flat" delta-hint="今日累计" :delay="4" count-up
          />
        </div>
      </section>

      <!-- ============ 图表区 ============ -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <!-- 全站打卡趋势（7天/30天 切换） -->
        <section class="dash-card p-5 lg:col-span-2 v-reveal delay-2">
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

        <!-- 失败原因分布（归类后） -->
        <section class="dash-card p-5 v-reveal delay-3">
          <h3 class="font-semibold text-ink mb-1">失败原因分布</h3>
          <p class="text-xs text-ink-muted mb-2">近 30 天 · 共 {{ failTotal }} 次失败</p>
          <BaseChart v-if="failTotal > 0" :option="failOption" height="290px" />
          <div v-else class="flex h-[290px] flex-col items-center justify-center gap-2 text-ink-muted">
            <Icon name="check-circle" :size="30" class="text-success/60" />
            <p class="text-sm">近 30 天没有失败记录</p>
          </div>
        </section>
      </div>

      <!-- ============ 账号健康卡（凭证异常 + 疑似漏签） ============ -->
      <section
        class="relative overflow-hidden rounded-2xl dash-card bg-gradient-to-br from-white via-white to-brand/[0.04] p-5 sm:p-6 v-reveal delay-3"
      >
        <!-- 氛围光斑：品牌色/琥珀色极低透明模糊，增加层次不抢数据 -->
        <div class="pointer-events-none absolute -right-16 -top-24 h-56 w-56 rounded-full bg-brand/[0.07] blur-3xl"></div>
        <div class="pointer-events-none absolute -left-12 -bottom-28 h-56 w-56 rounded-full bg-amber/[0.08] blur-3xl"></div>

        <div class="relative flex flex-wrap items-center justify-between gap-3 mb-6">
          <div>
            <h3 class="font-semibold text-ink">账号健康</h3>
            <p class="mt-0.5 text-xs text-ink-muted">全站 B 平台账号体检 · 凭证状态与漏签风险</p>
          </div>
          <span
            class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
            :class="allHealthy ? 'bg-success/10 text-success' : 'bg-amber/10 text-amber'"
          >
            <span class="h-1.5 w-1.5 rounded-full" :class="allHealthy ? 'bg-success' : 'bg-amber animate-pulse'"></span>
            {{ allHealthy ? '全部正常' : '需要关注' }}
          </span>
        </div>

        <div class="relative grid gap-6 lg:grid-cols-[auto_minmax(0,1fr)]">
          <!-- 左：双环仪表（GSAP 数字滚动 + 圆环补间） -->
          <div class="flex items-center justify-center gap-8">
            <div class="flex flex-col items-center gap-2">
              <div class="relative h-[108px] w-[108px]">
                <svg viewBox="0 0 100 100" class="h-full w-full -rotate-90">
                  <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(20,33,61,0.08)" stroke-width="8" />
                  <circle
                    ref="ringInvalid" cx="50" cy="50" r="42" fill="none" stroke-linecap="round" stroke-width="8"
                    :stroke="invalidTotal > 0 ? '#ef4444' : '#10b981'" stroke-dasharray="263.9"
                    style="stroke-dashoffset: 263.9px; filter: drop-shadow(0 0 6px rgba(239,68,68,0.22))"
                  />
                </svg>
                <div class="absolute inset-0 flex flex-col items-center justify-center">
                  <span class="text-2xl font-bold tabular-nums text-ink">{{ invalidNum }}</span>
                  <span class="mt-0.5 text-[10px] text-ink-muted">凭证异常</span>
                </div>
              </div>
              <p class="text-[11px] text-ink-muted">占全站账号 {{ invalidPct }}%</p>
            </div>

            <div class="flex flex-col items-center gap-2">
              <div class="relative h-[108px] w-[108px]">
                <svg viewBox="0 0 100 100" class="h-full w-full -rotate-90">
                  <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(20,33,61,0.08)" stroke-width="8" />
                  <circle
                    ref="ringStale" cx="50" cy="50" r="42" fill="none" stroke-linecap="round" stroke-width="8"
                    :stroke="staleTotal > 0 ? '#f59e0b' : '#10b981'" stroke-dasharray="263.9"
                    style="stroke-dashoffset: 263.9px; filter: drop-shadow(0 0 6px rgba(245,158,11,0.2))"
                  />
                </svg>
                <div class="absolute inset-0 flex flex-col items-center justify-center">
                  <span class="text-2xl font-bold tabular-nums text-ink">{{ staleNum }}</span>
                  <span class="mt-0.5 text-[10px] text-ink-muted">疑似漏签</span>
                </div>
              </div>
              <p class="text-[11px] text-ink-muted">占启用任务 {{ stalePct }}%</p>
            </div>
          </div>

          <!-- 右：两列明细 -->
          <div class="grid min-w-0 gap-4 sm:grid-cols-2">
            <div class="min-w-0">
              <p class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">凭证异常账号</p>
              <ul class="health-scroll space-y-1.5 overflow-y-auto pr-1 lg:max-h-44">
                <li
                  v-for="row in health.invalidCredentials.list"
                  :key="'ic' + row.account"
                  class="health-row flex items-center gap-2 rounded-lg bg-cloud/70 px-2.5 py-2 text-xs"
                >
                  <span class="h-1.5 w-1.5 shrink-0 rounded-full bg-red-500"></span>
                  <span class="min-w-0 flex-1 truncate text-ink-soft">{{ row.account }}</span>
                  <span class="hidden shrink-0 text-ink-muted sm:inline">{{ row.username }}</span>
                  <span class="shrink-0 rounded-full bg-red-500/10 px-1.5 py-0.5 text-[10px] text-red-600">
                    {{ row.verifyStatus === 'unverified' ? '未校验' : '已失效' }}
                  </span>
                </li>
                <li v-if="!health.invalidCredentials.list.length" class="rounded-lg bg-success/10 px-2.5 py-2 text-xs text-success">
                  全部账号凭证正常
                </li>
              </ul>
            </div>
            <div class="min-w-0">
              <p class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">疑似漏签任务</p>
              <ul class="health-scroll space-y-1.5 overflow-y-auto pr-1 lg:max-h-44">
                <li
                  v-for="row in health.staleSign.list"
                  :key="'st' + row.account + row.taskType"
                  class="health-row flex items-center gap-2 rounded-lg bg-cloud/70 px-2.5 py-2 text-xs"
                >
                  <span class="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500"></span>
                  <span class="min-w-0 flex-1 truncate text-ink-soft">{{ row.account }}</span>
                  <span class="hidden shrink-0 text-ink-muted sm:inline">{{ row.username }}</span>
                  <span class="shrink-0 rounded-full bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-600">
                    {{ row.days === null ? '从未签到' : `${row.days} 天未签` }}
                  </span>
                </li>
                <li v-if="!health.staleSign.list.length" class="rounded-lg bg-success/10 px-2.5 py-2 text-xs text-success">
                  无漏签风险任务
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <!-- ============ 额度健康：分桶直方图 + 预警列表 ============ -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section class="dash-card p-5 v-reveal delay-3">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="font-semibold text-ink">额度健康分布</h3>
              <p class="text-xs text-ink-muted mt-0.5">按使用率（账号数 / 额度上限）分桶 · 共 {{ summary.users }} 个用户</p>
            </div>
            <span class="rounded-full bg-amber/10 px-2.5 py-0.5 text-xs font-medium text-amber">预警阈值 {{ quota.warnRatio }}%</span>
          </div>
          <BaseChart :option="quotaOption" height="280px" />
        </section>

        <!-- 额度预警用户列表（Top 20） -->
        <section class="dash-card p-5 v-reveal delay-4 flex flex-col min-h-0">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-semibold text-ink">额度预警用户</h3>
            <span class="rounded-full bg-danger/10 px-2.5 py-0.5 text-xs font-medium text-danger">
              占用 ≥ {{ quota.warnRatio }}% · 共 {{ quota.warnTotal }} 人
            </span>
          </div>
          <div class="health-scroll overflow-y-auto lg:max-h-[340px]">
            <table class="w-full text-sm">
              <thead class="sticky top-0 bg-white">
                <tr class="text-left text-ink-muted border-b border-ink/5">
                  <th class="font-medium py-2.5 pr-4">用户</th>
                  <th class="font-medium py-2.5 pr-4 text-right">已用 / 上限</th>
                  <th class="font-medium py-2.5 pr-4">占用率</th>
                  <th class="font-medium py-2.5">状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="u in quota.warnUsers" :key="u.user_id" class="border-b border-ink/5 last:border-0">
                  <td class="py-3 pr-4 font-medium text-ink">{{ u.username }}</td>
                  <td class="py-3 pr-4 text-right text-ink-muted tabular-nums">{{ u.used }} / {{ u.quota }}</td>
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
                <tr v-if="!quota.warnUsers.length">
                  <td colspan="4" class="py-6 text-center text-ink-muted">当前没有达到预警阈值的用户</td>
                </tr>
              </tbody>
            </table>
            <p v-if="quota.warnTotal > quota.warnUsers.length" class="mt-3 text-xs text-ink-muted">
              仅展示前 {{ quota.warnUsers.length }} 名，其余 {{ quota.warnTotal - quota.warnUsers.length }} 人请到
              <RouterLink to="/users" class="text-brand hover:underline">用户管理</RouterLink> 查看。
            </p>
          </div>
        </section>
      </div>

      <!-- ============ 列表模块 ============ -->
      <section class="dash-card p-5 v-reveal delay-4">
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-semibold text-ink">高频失败风险用户</h3>
          <span class="rounded-full bg-danger/10 px-2.5 py-0.5 text-xs font-medium text-danger">近 7 天 · 失败 ≥ 3 次或失败率 ≥ 50%</span>
        </div>
        <div class="health-scroll overflow-y-auto lg:max-h-[420px]">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-ink-muted border-b border-ink/5">
                <th class="font-medium py-2.5 pr-4">用户</th>
                <th class="font-medium py-2.5 pr-4 text-right">执行次数</th>
                <th class="font-medium py-2.5 pr-4 text-right">失败次数</th>
                <th class="font-medium py-2.5 pr-4 text-right">失败率</th>
                <th class="font-medium py-2.5">最近失败原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in riskUsers" :key="u.username" class="border-b border-ink/5 last:border-0">
                <td class="py-3 pr-4 font-medium text-ink">{{ u.username }}</td>
                <td class="py-3 pr-4 text-right text-ink-muted tabular-nums">{{ u.total }}</td>
                <td class="py-3 pr-4 text-right font-medium text-danger tabular-nums">{{ u.fails }}</td>
                <td class="py-3 pr-4 text-right tabular-nums" :class="u.rate >= 50 ? 'text-danger' : 'text-amber'">{{ u.rate }}%</td>
                <td class="py-3 text-ink-muted">{{ u.lastFailReason || '—' }}</td>
              </tr>
              <tr v-if="!riskUsers.length">
                <td colspan="5" class="py-6 text-center text-ink-muted">近 7 天没有高风险用户</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 全局最新打卡日志 -->
      <section class="dash-card p-5 v-reveal delay-4">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h3 class="font-semibold text-ink">全局最新打卡日志</h3>
          <div class="flex flex-wrap items-center gap-2 sm:gap-3">
            <div class="relative w-40">
              <Icon name="search" :size="14" class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted" />
              <input
                v-model="fUser"
                type="text"
                placeholder="按用户名筛选…"
                class="h-8 w-full rounded-lg border border-ink/10 bg-white pl-8 pr-2 text-xs text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/10"
              />
            </div>
            <div class="w-32 sm:w-36">
              <BaseSelect v-model="fType" size="sm" :options="[{ label: '全部类型', value: 'all' }, { label: '寝室签到', value: 'dorm' }, { label: '活动签到', value: 'activity' }]" />
            </div>
          </div>
        </div>
        <div class="health-scroll overflow-y-auto lg:max-h-[420px]">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-ink-muted border-b border-ink/5">
                <th class="font-medium py-2.5 pr-4">时间</th>
                <th class="font-medium py-2.5 pr-4">用户</th>
                <th class="font-medium py-2.5 pr-4">姓名</th>
                <th class="font-medium py-2.5 pr-4">账号</th>
                <th class="font-medium py-2.5 pr-4">类型</th>
                <th class="font-medium py-2.5 pr-4">结果</th>
                <th class="font-medium py-2.5">说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in recentLogs.items" :key="r.id" class="border-b border-ink/5 last:border-0">
                <td class="py-3 pr-4 text-ink-muted tabular-nums">{{ r.time }}</td>
                <td class="py-3 pr-4 font-medium text-ink">{{ r.username }}</td>
                <td class="py-3 pr-4 text-ink-muted">{{ r.studentName || '—' }}</td>
                <td class="py-3 pr-4 text-ink-muted">{{ r.account }}</td>
                <td class="py-3 pr-4">
                  <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium" :class="r.type === '活动签到' ? 'bg-brand/10 text-brand' : 'bg-info/10 text-info'">
                    {{ r.type }}
                  </span>
                </td>
                <td class="py-3 pr-4">
                  <span class="inline-flex items-center gap-1.5 text-xs font-medium" :class="statusMeta[r.status].cls">
                    <span class="h-1.5 w-1.5 rounded-full" :class="statusMeta[r.status].dot"></span>
                    {{ statusMeta[r.status].label }}
                  </span>
                </td>
                <td class="py-3 text-ink-muted">{{ r.failReason || '—' }}</td>
              </tr>
              <tr v-if="!recentLogs.items.length"><td colspan="7" class="py-6 text-center text-ink-muted">当前筛选条件下无日志</td></tr>
            </tbody>
          </table>
        </div>
        <div class="mt-3 flex items-center justify-between text-xs text-ink-muted">
          <span>共 {{ recentLogs.total }} 条</span>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="rounded-lg border border-ink/10 px-3 py-1.5 font-medium text-ink-soft transition hover:bg-cloud disabled:cursor-not-allowed disabled:opacity-40"
              :disabled="recentLogs.page <= 1"
              @click="store.setLogFilters({ page: recentLogs.page - 1 })"
            >上一页</button>
            <span class="tabular-nums">第 {{ recentLogs.page }} / {{ logTotalPages }} 页</span>
            <button
              type="button"
              class="rounded-lg border border-ink/10 px-3 py-1.5 font-medium text-ink-soft transition hover:bg-cloud disabled:cursor-not-allowed disabled:opacity-40"
              :disabled="recentLogs.page >= logTotalPages"
              @click="store.setLogFilters({ page: recentLogs.page + 1 })"
            >下一页</button>
          </div>
        </div>
      </section>

      <!-- ============ 调度器运行状态 + 即将执行 ============ -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section class="dash-card p-5 v-reveal delay-5">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-semibold text-ink">调度器运行状态</h3>
            <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium" :class="scheduler.running ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'">
              <span class="h-1.5 w-1.5 rounded-full" :class="scheduler.running ? 'bg-success animate-pulse' : 'bg-danger'"></span>
              {{ scheduler.running ? '运行中' : '已暂停' }}
            </span>
          </div>
          <dl class="space-y-2.5 text-sm">
            <div class="flex items-center justify-between"><dt class="text-ink-muted">注册任务</dt><dd class="font-medium text-ink tabular-nums">{{ scheduler.jobCount }} 个</dd></div>
            <div class="flex items-center justify-between"><dt class="text-ink-muted">启用中任务</dt><dd class="font-medium text-ink tabular-nums">{{ schedulesEnabled }} 个</dd></div>
            <div class="flex items-center justify-between"><dt class="text-ink-muted">今日执行</dt><dd class="font-medium text-ink tabular-nums">{{ scheduler.todayRuns }} 次</dd></div>
            <div class="flex items-center justify-between"><dt class="text-ink-muted">下次执行</dt><dd class="font-medium text-ink tabular-nums">{{ nextRunText }}</dd></div>
          </dl>
        </section>

        <section class="dash-card p-5 lg:col-span-2 v-reveal delay-5">
          <h3 class="font-semibold text-ink mb-4">即将执行的任务</h3>
          <ul class="space-y-2">
            <li v-for="(n, i) in scheduler.nextRuns" :key="i" class="flex items-center gap-3 rounded-xl border border-ink/5 bg-ink/[0.02] px-3 py-2.5 text-sm">
              <span class="inline-flex items-center rounded-full bg-brand/10 px-2.5 py-0.5 text-xs font-medium text-brand">{{ n.taskLabel }}</span>
              <span class="min-w-0 flex-1 truncate font-medium text-ink">{{ n.account }}</span>
              <span class="shrink-0 text-ink-muted tabular-nums">{{ n.time }}</span>
            </li>
            <li v-if="!scheduler.nextRuns.length" class="rounded-xl bg-cloud/60 px-3 py-4 text-center text-sm text-ink-muted">
              暂无排队中的执行计划
            </li>
          </ul>
          <p class="mt-3 text-xs text-ink-muted">
            寝室签到按用户配置时间触发；活动签到按间隔轮询自动发现并提交（发现后随机延迟，防"秒签"暴露）。
          </p>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { gsap } from 'gsap'
import { storeToRefs } from 'pinia'
import StatCard from '@/components/StatCard.vue'
import BaseChart from '@/components/BaseChart.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import RefreshStrip from '@/components/RefreshStrip.vue'
import Icon from '@/components/Icon.vue'
import { useAdminOverviewStore } from '@/stores/adminOverview'

// [权限判断] 本页仅管理员可达（分发见 DashboardView；路由守卫二次校验）。
const store = useAdminOverviewStore()
const { data: dash, loading, refreshing, loaded } = storeToRefs(store)

const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

// ===== 概览引用 =====
const summary = computed(() => dash.value.summary)
const quota = computed(() => dash.value.quota)
const scheduler = computed(() => dash.value.scheduler)
const health = computed(() => dash.value.accountHealth)
const riskUsers = computed(() => dash.value.riskUsers)
// 日志区：store 未单出 recentLogs，从聚合数据派生并兜底空结构（首帧渲染安全）
const recentLogs = computed(() => dash.value.recentLogs || { items: [], total: 0, page: 1, page_size: 10 })
const schedulesEnabled = computed(() => dash.value.schedulesEnabled || 0)

// ===== 日志筛选（用户名防抖 400ms；类型即改即查；分页由按钮显式触发）=====
const fRange = ref('7d')
const fType = ref('all')
const fUser = ref('')
let userTimer = null
watch(fUser, (v) => {
  clearTimeout(userTimer)
  userTimer = setTimeout(() => store.setLogFilters({ username: v.trim() }), 400)
})
watch(fType, (v) => store.setLogFilters({ type: v }))

const logTotalPages = computed(() => Math.max(1, Math.ceil(recentLogs.value.total / (recentLogs.value.page_size || 10))))

// ===== 趋势图 =====
const trendSeries = computed(() => dash.value.trend[fRange.value] || [])
const trendOption = computed(() => ({
  grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
  tooltip: { trigger: 'axis' },
  legend: { data: ['成功', '失败', '跳过'], top: 0, textStyle: { color: '#6b7280', fontSize: 11 } },
  xAxis: { type: 'category', boundaryGap: false, data: trendSeries.value.map((d) => d.date), axisLine: { lineStyle: { color: '#e5e7eb' } } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f3f4f6' } } },
  series: [
    { name: '成功', type: 'line', smooth: true, symbolSize: 5, data: trendSeries.value.map((d) => d.success), itemStyle: { color: '#16a34a' }, areaStyle: { color: 'rgba(22,163,74,0.08)' } },
    { name: '失败', type: 'line', smooth: true, symbolSize: 5, data: trendSeries.value.map((d) => d.fail), itemStyle: { color: '#dc2626' } },
    { name: '跳过', type: 'line', smooth: true, symbolSize: 5, data: trendSeries.value.map((d) => d.skip), itemStyle: { color: '#d97706' } },
  ],
}))

// ===== 失败原因分布（归类后） =====
const failTotal = computed(() => dash.value.failCategories.reduce((n, c) => n + c.count, 0))
const FAIL_COLORS = ['#dc2626', '#d97706', '#2563eb', '#7c3aed', '#0891b2', '#65a30d', '#db2777', '#9ca3af']
const failOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} 次（{d}%）' },
  legend: { orient: 'vertical', right: 8, top: 'middle', textStyle: { color: '#6b7280', fontSize: 11 } },
  series: [{
    type: 'pie', radius: ['48%', '72%'], center: ['36%', '50%'],
    itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
    label: { show: false },
    data: dash.value.failCategories.map((c, i) => ({ name: c.category, value: c.count, itemStyle: { color: FAIL_COLORS[i % FAIL_COLORS.length] } })),
  }],
}))

// ===== 额度健康分桶 =====
const quotaOption = computed(() => {
  const b = quota.value.buckets
  const data = [
    { name: '未使用', value: b.unused, itemStyle: { color: '#cbd5e1' } },
    { name: '<50%', value: b.lt50, itemStyle: { color: '#93c5fd' } },
    { name: '50~79%', value: b.r50to79, itemStyle: { color: '#60a5fa' } },
    { name: '80~99%', value: b.r80to99, itemStyle: { color: '#d97706' } },
    { name: '已满', value: b.full, itemStyle: { color: '#dc2626' } },
  ]
  return {
    grid: { left: 8, right: 16, top: 30, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis', formatter: '{b}: {c} 人' },
    xAxis: { type: 'category', data: data.map((d) => d.name), axisLine: { lineStyle: { color: '#e5e7eb' } } },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#f3f4f6' } } },
    series: [{ type: 'bar', barWidth: 36, data, label: { show: true, position: 'top', color: '#6b7280' } }],
  }
})

// ===== 账号健康卡（圆环 + 数字 GSAP 补间；尊重减少动效偏好）=====
const C = 2 * Math.PI * 42
const invalidTotal = computed(() => health.value.invalidCredentials.total)
const staleTotal = computed(() => health.value.staleSign.total)
const invalidRate = computed(() => (summary.value.accounts ? Math.min(1, invalidTotal.value / summary.value.accounts) : 0))
const staleRate = computed(() => {
  const base = Math.max(1, dash.value.schedulesEnabled)
  return Math.min(1, staleTotal.value / base)
})
const invalidPct = computed(() => Math.round(invalidRate.value * 100))
const stalePct = computed(() => Math.round(staleRate.value * 100))
const allHealthy = computed(() => invalidTotal.value === 0 && staleTotal.value === 0)

const ringInvalid = ref(null)
const ringStale = ref(null)
const invalidNum = ref(0)
const staleNum = ref(0)
// 下次执行时间：调度器 nextRuns 的最早一条（cron 任务与轮询任务混合排序）
const nextRunText = computed(() => scheduler.value.nextRuns[0]?.time || '暂无排期')

function animateHealth() {
  const setFinal = () => {
    if (ringInvalid.value) ringInvalid.value.style.strokeDashoffset = String(C * (1 - invalidRate.value))
    if (ringStale.value) ringStale.value.style.strokeDashoffset = String(C * (1 - staleRate.value))
    invalidNum.value = invalidTotal.value
    staleNum.value = staleTotal.value
  }
  if (prefersReduced) return setFinal()
  const t = { a: 0, b: 0, na: 0, nb: 0 }
  gsap.to(t, {
    a: invalidRate.value, b: staleRate.value, na: invalidTotal.value, nb: staleTotal.value,
    duration: 1, ease: 'power2.out',
    onUpdate: () => {
      if (ringInvalid.value) ringInvalid.value.style.strokeDashoffset = String(C * (1 - t.a))
      if (ringStale.value) ringStale.value.style.strokeDashoffset = String(C * (1 - t.b))
      invalidNum.value = Math.round(t.na)
      staleNum.value = Math.round(t.nb)
    },
  })
  gsap.fromTo('.health-row', { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.35, stagger: 0.04, clearProps: 'opacity,transform' })
}

watch(() => dash.value.accountHealth, () => nextTick(animateHealth))
// 首载时健康卡在骨架屏之后才挂载，watch 触发时圆环 ref 尚为 null；
// loading 结束（骨架→真实内容）后再补一次动画
watch(loading, (v) => {
  if (!v && loaded.value) nextTick(animateHealth)
})

const statusMeta = {
  success: { label: '成功', cls: 'bg-success/10 text-success', dot: 'bg-success' },
  fail: { label: '失败', cls: 'bg-danger/10 text-danger', dot: 'bg-danger' },
  skip: { label: '跳过', cls: 'bg-amber/15 text-amber', dot: 'bg-amber' },
}

onMounted(() => {
  store.loadOverview()
})
</script>
