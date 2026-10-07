<template>

  <!-- 静默刷新期（回到页面后台换新）整页降透明，统计卡/图表原地换数，不闪加载态 -->

  <div class="space-y-6 transition-opacity" :class="refreshing && 'opacity-60 pointer-events-none'">

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

      <section class="dash-card p-5 lg:col-span-2 v-reveal delay-2">

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

      <section class="dash-card p-5 v-reveal delay-3">

        <h3 class="font-semibold text-ink mb-1">打卡类型分布</h3>

        <p class="text-xs text-ink-muted mb-2">近 30 天 · 共 {{ typeTotal }} 次打卡</p>

        <BaseChart :option="typeDistOption" height="290px" />

        <p v-if="!loading && typeTotal === 0" class="mt-2 text-center text-xs text-ink-muted">近 30 天暂无打卡数据</p>

      </section>

    </div>



    <!-- 我的调度状态 + 即将执行：左卡回望过去（最近执行时间轴），右卡展望未来（队列），
         两卡分工避免信息重复。任务计数/时间轴/推送统计全部仅限本人数据 -->
    <div class="grid grid-cols-1 lg:grid-cols-5 gap-4">
      <!-- 我的调度运行状态（过去视角） -->
      <section class="dash-card p-5 lg:col-span-2 v-reveal delay-3 flex flex-col">
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-semibold text-ink">我的调度状态</h3>
          <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium" :class="me.scheduler.running ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'">
            <span class="h-1.5 w-1.5 rounded-full" :class="me.scheduler.running ? 'bg-success animate-pulse' : 'bg-danger'"></span>
            {{ me.scheduler.running ? '运行中' : '已暂停' }}
          </span>
        </div>
        <p class="text-xs text-ink-muted mb-3">最近执行结果 · 最多 4 条</p>
        <!-- 执行结果时间轴：状态点着色（成功绿/失败红/跳过琥珀），复用 recentLogs 前 4 条 -->
        <ul v-if="timelineItems.length" class="relative ml-1 pl-5 space-y-1">
          <span class="absolute left-[5px] top-2 bottom-2 w-0.5 rounded-full bg-ink/10"></span>
          <li v-for="(t, i) in timelineItems" :key="t.id || i" class="relative flex items-start gap-3 py-1.5">
            <span class="absolute -left-5 top-[1.15em] h-3 w-3 rounded-full border-2 bg-elevated" :class="timelineDot(t.result)"></span>
            <span class="w-[72px] shrink-0 pt-0.5 text-xs text-ink-muted tabular-nums">{{ t.timelineTime }}</span>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="min-w-0 flex-1 truncate text-sm font-medium text-ink">{{ t.name || t.account || '—' }}</span>
                <span class="inline-flex shrink-0 items-center gap-1.5 text-xs font-medium" :class="statusMeta[t.result].cls">
                  <span class="h-1.5 w-1.5 rounded-full" :class="dotCls(t.result)"></span>{{ statusMeta[t.result].label }}
                </span>
              </div>
              <p class="mt-0.5 truncate text-xs text-ink-muted" :title="`${t.type} · ${t.note || '—'}`">{{ t.type }} · {{ t.note || '—' }}</p>
            </div>
          </li>
        </ul>
        <p v-else class="rounded-xl bg-cloud/60 px-3 py-4 text-center text-sm text-ink-muted">暂无执行记录</p>
        <!-- 调度质量统计：类型分列展示启用任务；近 30 天成功率/累计执行补足留白 -->
        <div class="mt-auto grid grid-cols-4 gap-3 border-t border-ink/5 pt-4">
          <div>
            <p class="font-semibold text-ink tabular-nums">{{ me.tasks.active }}<span class="ml-0.5 text-xs font-normal text-ink-muted">个</span></p>
            <p class="mt-0.5 text-xs text-ink-muted">启用任务</p>
            <p class="text-[11px] text-ink-muted/80">寝 {{ me.scheduler.taskTypes.dorm }} · 活 {{ me.scheduler.taskTypes.activity }}</p>
          </div>
          <div>
            <p class="font-semibold text-ink tabular-nums">{{ me.scheduler.jobCount }}<span class="ml-0.5 text-xs font-normal text-ink-muted">个</span></p>
            <p class="mt-0.5 text-xs text-ink-muted">已注册定时</p>
            <p v-if="me.scheduler.unregistered" class="text-[11px] text-amber">课表接管 {{ me.scheduler.unregistered }}</p>
            <p v-else class="text-[11px] text-ink-muted/80">&nbsp;</p>
          </div>
          <div>
            <p class="font-semibold tabular-nums" :class="rateTextCls(successRate)">{{ successRate }}<span class="ml-0.5 text-xs font-normal text-ink-muted">%</span></p>
            <p class="mt-0.5 text-xs text-ink-muted">近 30 天成功率</p>
            <p class="text-[11px] text-ink-muted/80">&nbsp;</p>
          </div>
          <div>
            <p class="font-semibold text-ink tabular-nums">{{ me.scheduler.runTotal ?? 0 }}<span class="ml-0.5 text-xs font-normal text-ink-muted">次</span></p>
            <p class="mt-0.5 text-xs text-ink-muted">累计执行</p>
            <p class="text-[11px] text-ink-muted/80">&nbsp;</p>
          </div>
        </div>
      </section>

      <!-- 即将执行（未来视角，仅本人任务，最多 5 条；带 x 小时/天后执行口径） -->
      <section class="dash-card p-5 lg:col-span-3 v-reveal delay-3">
        <h3 class="font-semibold text-ink mb-4">即将执行的任务</h3>
        <ul class="space-y-2">
          <li v-for="(n, i) in me.scheduler.nextRuns" :key="i" class="flex items-start gap-3 rounded-xl border border-ink/5 bg-ink/[0.02] px-3 py-2.5 text-sm">
            <span class="inline-flex shrink-0 items-center rounded-full bg-brand/10 px-2.5 py-0.5 text-xs font-medium text-brand">{{ n.taskLabel }}</span>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="min-w-0 flex-1 truncate font-medium text-ink">{{ n.account }}</span>
                <span class="shrink-0 text-xs text-ink-muted tabular-nums">{{ n.time }}</span>
                <span v-if="inText(n)" class="shrink-0 rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-medium text-brand">{{ inText(n) }}</span>
              </div>
              <p v-if="n.studentName" class="mt-0.5 truncate text-xs text-ink-muted">姓名 {{ n.studentName }}</p>
            </div>
          </li>
          <li v-if="!me.scheduler.nextRuns.length" class="rounded-xl bg-cloud/60 px-3 py-4 text-center text-sm text-ink-muted">
            暂无排队中的执行计划
          </li>
        </ul>
        <p class="mt-3 text-xs text-ink-muted">
          寝室签到按配置时间触发；活动签到按间隔轮询自动发现并提交（发现后随机延迟，防"秒签"暴露）。
        </p>
      </section>
    </div>

    <!-- 我的推送送达（近 7 天）：口径与管理员侧一致——送达率分母只含真实发出的推送，
         未发送（没配凭证等）单列不计入分母，避免把「没配」误读成「通道坏了」 -->
    <section class="dash-card p-5 v-reveal delay-3">
      <div class="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <h3 class="font-semibold text-ink">我的推送送达</h3>
          <p class="mt-0.5 text-xs text-ink-muted">
            近 {{ me.pushHealth.days }} 天 · 送达率只统计真实发出的推送，未发送单列、不计入分母
          </p>
        </div>
        <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium" :class="PUSH_TONE[pushTone].cls">
          <span class="h-1.5 w-1.5 rounded-full" :class="PUSH_TONE[pushTone].dot"></span>
          {{ pushBadge }}
        </span>
      </div>

      <p v-if="pushEmpty" class="rounded-xl bg-cloud/60 px-3 py-6 text-center text-sm text-ink-muted">
        近 {{ me.pushHealth.days }} 天没有推送记录
      </p>

      <template v-else>
        <div class="flex flex-wrap items-baseline gap-x-6 gap-y-2">
          <div>
            <span class="text-2xl font-bold tabular-nums text-ink">{{ me.pushHealth.summary.sent }}</span>
            <span class="ml-1 text-xs text-ink-muted">次真实发送</span>
          </div>
          <div>
            <span class="text-2xl font-bold tabular-nums" :class="rateTextCls(me.pushHealth.summary.rate)">
              {{ me.pushHealth.summary.rate === null ? '—' : me.pushHealth.summary.rate }}<span
                v-if="me.pushHealth.summary.rate !== null" class="text-base">%</span>
            </span>
            <span class="ml-1 text-xs text-ink-muted">送达率</span>
          </div>
          <div class="text-xs text-ink-muted">
            成功 <span class="font-medium tabular-nums text-success">{{ me.pushHealth.summary.ok }}</span>
            · 失败 <span class="font-medium tabular-nums text-danger">{{ me.pushHealth.summary.fail }}</span>
            · 未发送 <span class="font-medium tabular-nums text-amber">{{ me.pushHealth.summary.skipped }}</span>
          </div>
        </div>

        <div class="mt-5 grid gap-6 lg:grid-cols-2">
          <!-- 左：按通道 -->
          <div class="min-w-0">
            <div class="mb-2 flex items-center justify-between gap-2">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">按通道</p>
              <span class="text-[11px] text-ink-muted">{{ me.pushHealth.summary.channels }} 个通道有发送</span>
            </div>
            <ul class="space-y-1.5">
              <li v-for="c in me.pushHealth.byChannel" :key="'ch' + c.channel"
                  class="flex items-center gap-2.5 rounded-lg bg-cloud/70 px-2.5 py-2 text-xs">
                <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="channelDot(c.channel)"></span>
                <span class="w-16 shrink-0 truncate font-medium text-ink">{{ channelLabel(c.channel) }}</span>
                <span class="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-ink/10">
                  <span class="block h-full rounded-full" :class="rateBarCls(c.rate)" :style="{ width: (c.rate || 0) + '%' }"></span>
                </span>
                <span class="w-9 shrink-0 text-right tabular-nums" :class="rateTextCls(c.rate)">
                  {{ c.rate === null ? '—' : c.rate + '%' }}
                </span>
                <span class="w-24 shrink-0 text-right text-[11px] text-ink-muted tabular-nums">
                  {{ c.sent }} 发<span v-if="c.fail"> · <span class="text-danger">{{ c.fail }} 失败</span></span><span v-if="c.skipped"> · {{ c.skipped }} 未发</span>
                </span>
              </li>
              <li v-if="!me.pushHealth.byChannel.length" class="rounded-lg bg-cloud/60 px-2.5 py-2 text-xs text-ink-muted">
                没有通道产生过发送
              </li>
            </ul>
          </div>

          <!-- 右：签到成功但通知未送达（本人视角的推送异常清单） -->
          <div class="min-w-0">
            <div class="mb-2 flex items-center justify-between gap-2">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">签到成功但通知未送达</p>
              <span v-if="me.pushHealth.signOkPushFail.total > me.pushHealth.signOkPushFail.list.length" class="text-[11px] text-ink-muted">
                共 {{ me.pushHealth.signOkPushFail.total }} 条
              </span>
            </div>
            <ul class="space-y-1.5">
              <li v-for="x in me.pushHealth.signOkPushFail.list" :key="'pf' + x.time + x.channel"
                  class="rounded-lg px-2.5 py-2 text-xs" :class="x.skipped ? 'bg-amber/[0.08]' : 'bg-danger/[0.06]'">
                <div class="flex items-center gap-2">
                  <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="x.skipped ? 'bg-amber' : 'bg-danger'"></span>
                  <span class="min-w-0 flex-1 truncate font-medium text-ink">
                    {{ x.account || '未知账号' }}
                  </span>
                  <span class="shrink-0 text-[11px] text-ink-muted tabular-nums">{{ x.time }}</span>
                </div>
                <p class="mt-1 truncate pl-3.5 text-[11px] text-ink-muted" :title="x.error">
                  <span class="font-medium" :class="x.skipped ? 'text-amber' : 'text-danger'">{{ x.skipped ? '未发送' : '发送失败' }}</span>
                  · {{ channelLabel(x.channel) }}<template v-if="x.error"> · {{ x.error }}</template>
                </p>
              </li>
              <li v-if="!me.pushHealth.signOkPushFail.list.length" class="rounded-lg bg-success/10 px-2.5 py-2 text-xs text-success">
                签到成功的通知全部送达
              </li>
            </ul>
          </div>
        </div>
      </template>
    </section>

    <!-- 两卡保持默认 stretch 等高：曾用 lg:items-start 让它们各按自身高度落位，结果是
         底边参差最多 204px。留白改由「谁的内容能长」来吸收——图表容器 flex-1、账号空态居中。 -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">

      <!-- 任务完成情况 -->

      <section class="dash-card p-5 v-reveal delay-3 flex flex-col">

        <h3 class="font-semibold text-ink mb-1">任务完成情况</h3>

        <p class="text-xs text-ink-muted mb-2">近 30 天 · 执行结果占比</p>

        <!-- 不给固定像素高、由 flex-1 撑满卡片剩余高度：被同排账号卡拉高时多出的空间落进画布，

             而不是在卡底留一块空白。⚠️必须留 min-h 下限——饼图 radius 是 min(宽,高) 的百分比，

             实测 368 宽下 260px 画布 = 198px 圆环、118px 画布只有 90px，低于下限圆环会缩水。 -->

        <!-- contain:size 掐掉画布内在高对本行 auto 轨道尺寸的贡献：ECharts 画布是行内替换元素、
             宽高被写成像素，若参与轨道计算会把本行高度钉在「上次画布大小」上，形成不动点——
             同排账号卡展开一次后，收起时整行也收不回去。掐掉后本行高度只由卡片自身内容决定。 -->
        <BaseChart class="flex-1 min-h-[260px]" :style="{ contain: 'size' }" :option="taskOption" />

        <p v-if="!loading && taskSummaryTotal === 0" class="mt-2 text-center text-xs text-ink-muted">近 30 天暂无执行记录</p>

      </section>



      <!-- 我的账号状态（仅显示已启用并配置好配置套的账号） -->

      <section class="dash-card p-5 lg:col-span-2 v-reveal delay-4 flex flex-col">

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

        <!-- 空态占满剩余高度并垂直居中：没有账号时这段只有 ~112px，被同排图表卡拉到

             卡片高度后内容会贴顶、下面空一大片 -->

        <div v-else-if="me.accounts.items.length === 0" class="flex flex-1 flex-col items-center justify-center py-8 text-center">

          <p class="text-sm text-ink-muted">还没有已启用并配置好配置套的账号</p>

          <RouterLink to="/sign-config" class="mt-2 inline-block text-sm font-medium text-brand hover:underline">去签到配置启用</RouterLink>

        </div>

        <template v-else>

          <!-- 展开态条数无业务上限，故给列表卡加限高 + 卡内滚动：426px = 3 行整

               （单卡 134px = 内容 100 + p-4 32 + 边框 2，行距 gap-3 12px）。

               只在桌面生效，移动端沿用文档流自然滚动（同 5bf19f1） -->

          <div ref="accountsGrid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 lg:max-h-[426px] lg:overflow-y-auto lg:pr-1">

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

                <span class="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium" :class="accountTypeMetaByCode(a.typeCode).cls">{{ accountTypeMetaByCode(a.typeCode).label }}</span>

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

          <button v-if="me.accounts.items.length > ACCOUNT_LIMIT" @click="toggleAccounts"

                  class="mt-3 mx-auto flex items-center gap-1 text-sm font-medium text-brand hover:underline">

            {{ accountsExpanded ? '收起' : `展开全部 ${me.accounts.items.length} 个账号` }}

            <Icon :name="accountsExpanded ? 'chevron-up' : 'chevron-down'" :size="14" />

          </button>

        </template>

      </section>

    </div>



    <!-- ============ 我的最近签到日志 ============ -->

    <section class="dash-card p-5 v-reveal delay-4">

      <div class="flex items-center justify-between gap-3 mb-4">

        <h3 class="font-semibold text-ink">我的最近签到日志</h3>

        <div class="flex items-center gap-2 sm:gap-3">

          <div class="w-32 sm:w-36">

            <BaseSelect v-model="fType" size="sm" :options="[{ label: '全部类型', value: 'all' }, { label: '活动签到', value: 'activity' }, { label: '寝室签到', value: 'dorm' }]" />

          </div>

          <RouterLink to="/task-logs" class="shrink-0 text-sm font-medium text-brand hover:underline">查看全部</RouterLink>

        </div>

      </div>

      <!-- 高度 = 表头 41 + 行高 45 × 8 条 = 401px；限高按管理员打卡日志口径取 491px。

           后端 recent_logs 已限 8 条，此处是兜底：条数上调时也不会把卡片撑长。

           表头吸顶，卡内滚动时不丢列名。 -->

      <div class="overflow-auto lg:max-h-[491px]">

        <table class="w-full text-sm">

          <thead class="sticky top-0 z-10 bg-elevated">

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

                <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium" :class="taskTypeMeta(r.taskType).cls">

                  {{ taskTypeMeta(r.taskType).label }}

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

                  :to="{ path: '/task-logs', query: { accountId: r.accountId, type: r.taskType, status: 'fail' } }"

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

import { ref, computed, onMounted, nextTick } from 'vue'

import { RouterLink } from 'vue-router'

import { storeToRefs } from 'pinia'

import { gsap } from 'gsap'

import StatCard from '@/components/StatCard.vue'

import Icon from '@/components/Icon.vue'

import BaseSelect from '@/components/BaseSelect.vue'

import BaseChart from '@/components/BaseChart.vue'

import { useDashboardStore } from '@/stores/dashboard'
import { useThemeStore, lineSeries, overlapZOrder, withAlpha } from '@/stores/theme'
import { accountTypeMetaByCode, taskTypeMeta } from '@/utils/accountType'
import { channelDot, channelLabel } from '@/utils/pushChannels'



const store = useDashboardStore()

const themeStore = useThemeStore()

const { overview: me, loading, refreshing } = storeToRefs(store)



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

// 层序：数值小的系列画在上层，否则它整条被后画的系列压住、鼠标永远点不亮

const trendZ = computed(() => overlapZOrder(activeTrend.value, ['success', 'fail', 'skip']))

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
  (me.value.recentLogs || []).filter((r) => fType.value === 'all' || r.taskType === fType.value)
)

// ===== 我的调度状态（口径对齐管理员侧：running 为调度器服务级状态，任务数据仅限本人）=====
// 时间轴：复用 recentLogs 前 4 条（过去视角），右卡队列负责未来，两卡分工不重复
const timelineItems = computed(() => (me.value.recentLogs || []).slice(0, 4).map((r) => ({
  ...r,
  // recentLogs.time 是 "YYYY-MM-DD HH:MM"，时间轴收窄为 "MM-DD HH:MM"
  timelineTime: (r.time || '').replace(/^\d{4}-/, ''),
})))
const timelineDot = (result) => ({ success: 'border-success', fail: 'border-danger', skip: 'border-amber' }[result] || 'border-ink/30')

// 执行口径统一：<60min → "x 分钟后执行"；<24h → "x 小时后执行"；≥24h → "x 天后执行"
const inText = (n) => {
  const mins = n?.inMinutes
  if (mins === null || mins === undefined) return ''
  if (mins < 60) return `${Math.max(1, mins)} 分钟后执行`
  if (mins < 1440) return `${Math.floor(mins / 60)} 小时后执行`
  return `${Math.floor(mins / 1440)} 天后执行`
}

// ===== 我的推送送达（口径对齐管理员侧：分母只含真实发送，未发送单列）=====
const PUSH_TONE = {
  success: { cls: 'bg-success/10 text-success', dot: 'bg-success' },
  amber: { cls: 'bg-amber/10 text-amber', dot: 'bg-amber' },
  danger: { cls: 'bg-danger/10 text-danger', dot: 'bg-danger animate-pulse' },
}
const pushUndelivered = computed(() => (me.value.pushHealth?.summary?.fail || 0) + (me.value.pushHealth?.summary?.skipped || 0))
const pushEmpty = computed(() => !(me.value.pushHealth?.summary?.sent || 0) && !(me.value.pushHealth?.summary?.skipped || 0))
// 有真失败才算 danger；清一色「没发出去」是配置问题不是通道故障，用 amber 区分严重度
const pushTone = computed(() => {
  if ((me.value.pushHealth?.summary?.fail || 0) > 0) return 'danger'
  if (pushUndelivered.value > 0) return 'amber'
  return 'success'
})
const pushBadge = computed(() => {
  const n = pushUndelivered.value
  if (!n) return '全部送达'
  return pushTone.value === 'danger' ? `${n} 条未送达` : `${n} 条未发送`
})
// 送达率分档：≥95 正常 / ≥80 留意 / 更低告警（无发送记录时不表态）
const rateTextCls = (r) => (r === null ? 'text-ink-muted' : r >= 95 ? 'text-success' : r >= 80 ? 'text-amber' : 'text-danger')
const rateBarCls = (r) => (r === null ? 'bg-ink/20' : r >= 95 ? 'bg-success' : r >= 80 ? 'bg-amber' : 'bg-danger')



// ===== 账号卡片：默认只展示前 N 个，超出可展开（避免拉伸/显示不全）=====

const ACCOUNT_LIMIT = 6

const accountsExpanded = ref(false)

const visibleAccounts = computed(() => {

  const items = me.value.accounts.items || []

  return accountsExpanded.value ? items : items.slice(0, ACCOUNT_LIMIT)

})

// 展开 / 收起：按「当前高度 → 换条数后的自然高」补间，卡片高度平滑增长或回落。
// 高度不能交给 CSS 过渡（终值是 auto/受 max-h 约束的自然高，无法用 CSS 表达），故用 GSAP 补间像素值，
// 到位后 clearProps 交还 lg:max-h 与内容自身的高度，后续自适应（改窗口宽度、账号增减）不受内联值干扰。
const accountsGrid = ref(null)

let accountsTween = null

const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

async function toggleAccounts() {

  const el = accountsGrid.value

  const from = el ? el.getBoundingClientRect().height : 0

  accountsExpanded.value = !accountsExpanded.value

  await nextTick()

  if (!el) return

  const to = el.getBoundingClientRect().height

  if (accountsTween) { accountsTween.kill(); accountsTween = null }

  if (prefersReduced || from === to) return

  accountsTween = gsap.fromTo(el, { height: from }, {

    height: to,

    duration: 0.32,

    ease: 'power2.out',

    onComplete: () => {

      gsap.set(el, { clearProps: 'height' })

      accountsTween = null

    }

  })

}

// 头像首字：优先姓名，缺失回退登录账号

const initialOf = (a) => (a.name || a.account || '?').charAt(0)



// ===== 图表配色（令牌真值见 stores/theme.js::chart）=====

// ECharts 是 canvas 渲染、不解析 CSS 变量，故色值一律取 store 的 chart（读计算样式）。

// getter 形式保住 computed 的依赖追踪：切色相或切明暗时引用 C.* 的 option 会重新求值，

// BaseChart 的 deep watch 自动重绘。寝室系列取 brand、活动系列取 activity（默认即 info，

// 撞色相的主题在色板单独覆盖），与两处徽标的取色口径一致——图表与徽标说的必须是同一种颜色。

const C = {

  get success()  { return themeStore.chart.success },

  get fail()     { return themeStore.chart.danger },

  get skip()     { return themeStore.chart.amber },

  get brand()    { return themeStore.chart.brand },

  get activity() { return themeStore.chart.activity },

  get ink()      { return themeStore.chart.ink },

  get grid()     { return themeStore.chart.grid },

  get axis()     { return themeStore.chart.axis },

  get border()   { return themeStore.chart.border },

}



const trendOption = computed(() => ({

  grid: { left: 44, right: 18, top: 40, bottom: 28 },

  tooltip: {

    trigger: 'axis',

    backgroundColor: withAlpha(themeStore.meta.panel, 0.92), borderWidth: 0, padding: [6, 10],

    textStyle: { color: '#fff', fontSize: 12 },

    axisPointer: { type: 'line', lineStyle: { color: C.brand, type: 'dashed' } }

  },

  legend: { top: 0, right: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: C.ink, fontSize: 12 } },

  xAxis: {

    type: 'category', boundaryGap: false, data: activeTrend.value.map((p) => p.date),

    axisLine: { lineStyle: { color: C.axis } }, axisTick: { show: false },

    axisLabel: { color: C.ink, fontSize: 12, interval: fRange.value === '30d' ? 4 : 0 }

  },

  yAxis: { type: 'value', min: 0, axisLabel: { color: C.ink, fontSize: 12 }, splitLine: { lineStyle: { color: C.grid, type: 'dashed' } } },

  series: [

    lineSeries('成功', activeTrend.value.map((p) => p.success), C.success, C.border, trendZ.value.success),

    lineSeries('失败', activeTrend.value.map((p) => p.fail), C.fail, C.border, trendZ.value.fail),

    lineSeries('跳过', activeTrend.value.map((p) => p.skip), C.skip, C.border, trendZ.value.skip),

  ]

}))



const typeDistOption = computed(() => ({

  tooltip: { trigger: 'item', backgroundColor: withAlpha(themeStore.meta.panel, 0.92), borderWidth: 0, textStyle: { color: '#fff', fontSize: 12 }, formatter: '{b}：{c} 次 ({d}%)' },

  legend: { bottom: 0, textStyle: { color: C.ink, fontSize: 11 }, type: 'scroll' },

  series: [{

    type: 'pie', radius: ['46%', '70%'], center: ['50%', '42%'], avoidLabelOverlap: true,

    label: { show: false },

    itemStyle: { borderColor: C.border, borderWidth: 2, borderRadius: 6 },

    emphasis: { scale: true, scaleSize: 6 },

    data: [

      { value: me.value.typeDist?.activity || 0, name: '活动签到', itemStyle: { color: C.activity } },

      { value: me.value.typeDist?.dorm || 0, name: '寝室签到', itemStyle: { color: C.brand } }

    ]

  }]

}))



const taskOption = computed(() => ({

  tooltip: { trigger: 'item', backgroundColor: withAlpha(themeStore.meta.panel, 0.92), borderWidth: 0, textStyle: { color: '#fff', fontSize: 12 }, formatter: '{b}：{c} 次 ({d}%)' },

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

    itemStyle: { borderColor: C.border, borderWidth: 2, borderRadius: 6 },

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

