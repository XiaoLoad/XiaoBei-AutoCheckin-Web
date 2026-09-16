<template>
  <div ref="pageRef" class="space-y-6">
    <!--
      ============================================================
      管理员仪表盘（A 平台 · 对接外部 B 打卡平台）
      [权限判断] 本页仅管理员可访问；数据全部来自 /api/admin/overview
      真实聚合端点（用户/账号/签到记录/调度器），无 mock。
      多用户策略：仪表盘只呈现「聚合 + Top-N + 阈值分桶」，
      全量明细归属用户管理页。
      ============================================================
    -->

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
        class="relative overflow-hidden rounded-2xl dash-card bg-gradient-to-br from-card via-card to-brand/[0.04] p-5 sm:p-6 v-reveal delay-3"
      >
        <!-- 氛围光斑：品牌色/琥珀色极低透明模糊，增加层次不抢数据 -->
        <div class="pointer-events-none absolute -right-16 -top-24 h-56 w-56 rounded-full bg-brand/[0.07] blur-3xl"></div>
        <div class="pointer-events-none absolute -left-12 -bottom-28 h-56 w-56 rounded-full bg-amber/[0.08] blur-3xl"></div>

        <!-- 分母写在副标题里：环下方的百分比只有配上分母才读得出量级 -->
        <div class="relative flex flex-wrap items-start justify-between gap-3 mb-5">
          <div>
            <h3 class="font-semibold text-ink">账号健康</h3>
            <p class="mt-0.5 text-xs text-ink-muted">
              全站 <span class="tabular-nums text-ink-soft">{{ summary.accounts }}</span> 个账号
              · <span class="tabular-nums text-ink-soft">{{ summary.accountsEnabled }}</span> 个启用中
              · <span class="tabular-nums text-ink-soft">{{ schedulesEnabled }}</span> 个启用任务
            </p>
          </div>
          <!-- 二元徽标升级为带计数：此前 1 项异常与 50 项异常显示同一句话 -->
          <span
            class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
            :class="hasRisk ? 'bg-amber/10 text-warning' : 'bg-success/10 text-success'"
          >
            <span class="h-1.5 w-1.5 rounded-full" :class="hasRisk ? 'bg-amber animate-pulse' : 'bg-success'"></span>
            {{ hasRisk ? `${riskTotal} 项待处理` : '全部正常' }}
          </span>
        </div>

        <div class="relative grid gap-6 lg:grid-cols-[auto_minmax(0,1fr)]">
          <!-- 左：双环（GSAP 数字滚动 + 圆环补间）。
               最外一圈 60 格刻度是满量程参照——只有光秃圆环时，「占 4%」这个比例
               只能靠读环下那行小字，图形本身不表达量级。
               ⚠️ stroke-dashoffset 的初值必须走 SVG 属性而非 :style：GSAP 直接改
               inline style，而 :style 绑定在重渲染时会把它写回初值、抹掉补间进度。 -->
          <div class="flex items-center justify-center gap-7 sm:gap-9">
            <div class="flex flex-col items-center gap-2">
              <div class="relative h-[104px] w-[104px]">
                <svg viewBox="0 0 100 100" class="h-full w-full -rotate-90">
                  <circle cx="50" cy="50" r="47" fill="none" :stroke="CH.ring" stroke-width="1.6" stroke-dasharray="1.5 3.422" />
                  <circle cx="50" cy="50" r="42" fill="none" :stroke="CH.ringTrack" stroke-width="8" />
                  <circle
                    ref="ringInvalid" cx="50" cy="50" r="42" fill="none" stroke-linecap="round" stroke-width="8"
                    :stroke="invalidTotal > 0 ? ringDanger : ringOk"
                    stroke-dasharray="263.9" stroke-dashoffset="263.9"
                    :style="{ filter: ringGlow(invalidTotal > 0, 'invalid') }"
                  />
                </svg>
                <div class="absolute inset-0 flex flex-col items-center justify-center">
                  <span class="text-2xl font-bold tabular-nums text-ink">{{ invalidNum }}</span>
                  <span class="mt-0.5 text-[10px] text-ink-muted">凭证异常</span>
                </div>
              </div>
              <p class="text-[11px] text-ink-muted">
                占 <span class="tabular-nums text-ink-soft">{{ invalidPct }}</span>%
              </p>
            </div>

            <div class="flex flex-col items-center gap-2">
              <div class="relative h-[104px] w-[104px]">
                <svg viewBox="0 0 100 100" class="h-full w-full -rotate-90">
                  <circle cx="50" cy="50" r="47" fill="none" :stroke="CH.ring" stroke-width="1.6" stroke-dasharray="1.5 3.422" />
                  <circle cx="50" cy="50" r="42" fill="none" :stroke="CH.ringTrack" stroke-width="8" />
                  <circle
                    ref="ringStale" cx="50" cy="50" r="42" fill="none" stroke-linecap="round" stroke-width="8"
                    :stroke="staleTotal > 0 ? ringAmber : ringOk"
                    stroke-dasharray="263.9" stroke-dashoffset="263.9"
                    :style="{ filter: ringGlow(staleTotal > 0, 'stale') }"
                  />
                </svg>
                <div class="absolute inset-0 flex flex-col items-center justify-center">
                  <span class="text-2xl font-bold tabular-nums text-ink">{{ staleNum }}</span>
                  <span class="mt-0.5 text-[10px] text-ink-muted">疑似漏签</span>
                </div>
              </div>
              <p class="text-[11px] text-ink-muted">
                占 <span class="tabular-nums text-ink-soft">{{ stalePct }}</span>%
              </p>
            </div>
          </div>

          <!-- 右：两列明细。
               两列都是三行式卡片且第三行固定 16px 高：左列第三行是文字、右列是细条，
               不定高的话两列行高会差 7px 并随条数累积错位。
               列表限高 240px = 三条整（实测单行 76px + 间距 6px），改成 max-h-52 只露得出半条。 -->
          <div class="grid min-w-0 gap-4 sm:grid-cols-2">
            <div class="min-w-0">
              <div class="mb-2 flex items-baseline justify-between gap-2">
                <p class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">凭证异常账号</p>
                <span v-if="health.invalidCredentials.total" class="shrink-0 text-[11px] tabular-nums text-ink-muted">
                  共 {{ health.invalidCredentials.total }}
                </span>
              </div>
              <ul class="health-scroll space-y-1.5 overflow-y-auto pr-1 lg:max-h-60">
                <li
                  v-for="row in health.invalidCredentials.list"
                  :key="'ic' + row.account"
                  class="health-row rounded-lg bg-cloud/70 px-2.5 py-2 text-xs"
                >
                  <!-- 两行式卡片：首行账号 + 状态徽标，次行归属用户。
                       两列列表共用同一结构，行内各列左右缘才会跨行跨列对齐
                       （此前账号 flex-1 + 尾随 shrink-0 项宽度不定，中间那列会随内容左右飘） -->
                  <div class="flex items-center gap-2">
                    <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="row.verifyStatus === 'unverified' ? 'bg-warning' : 'bg-danger'"></span>
                    <span class="min-w-0 flex-1 truncate font-medium text-ink tabular-nums">{{ row.account }}</span>
                    <span
                      class="shrink-0 rounded-full px-1.5 py-0.5 text-[10px]"
                      :class="row.verifyStatus === 'unverified' ? 'bg-warning/10 text-warning' : 'bg-danger/10 text-danger'"
                    >
                      {{ row.verifyStatus === 'unverified' ? '未校验' : '已失效' }}
                    </span>
                  </div>
                  <p class="mt-1 truncate pl-3.5 text-[11px] text-ink-muted">{{ row.username || '未绑定用户' }}</p>
                  <p class="mt-1 flex h-4 items-center gap-1 pl-3.5 text-[10px] text-ink-muted">
                    <span class="shrink-0">校验于</span>
                    <span class="min-w-0 truncate tabular-nums text-ink-soft">{{ row.checkedAt || '从未校验' }}</span>
                  </p>
                </li>
                <li v-if="!health.invalidCredentials.list.length" class="rounded-lg bg-success/10 px-2.5 py-2 text-xs text-success">
                  全部账号凭证正常
                </li>
              </ul>
            </div>
            <div class="min-w-0">
              <div class="mb-2 flex items-baseline justify-between gap-2">
                <p class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">疑似漏签任务</p>
                <!-- 总量与量程都要写：条形的量程不写出来，读者无从判断「一半长」意味着一半什么 -->
                <span v-if="health.staleSign.total" class="shrink-0 text-[11px] tabular-nums text-ink-muted">
                  共 {{ health.staleSign.total }} · 刻度 {{ STALE_BAR_DAYS }} 天
                </span>
              </div>
              <ul class="health-scroll space-y-1.5 overflow-y-auto pr-1 lg:max-h-60">
                <li
                  v-for="row in health.staleSign.list"
                  :key="'st' + row.account + row.taskType"
                  class="health-row rounded-lg bg-cloud/70 px-2.5 py-2 text-xs"
                >
                  <div class="flex items-center gap-2">
                    <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="row.days === null ? 'bg-danger' : 'bg-amber'"></span>
                    <span class="min-w-0 flex-1 truncate font-medium text-ink tabular-nums">{{ row.account }}</span>
                    <span
                      class="shrink-0 rounded-full px-1.5 py-0.5 text-[10px]"
                      :class="row.days === null ? 'bg-danger/10 text-danger' : 'bg-amber/15 text-warning'"
                    >
                      {{ row.days === null ? '从未签到' : `${row.days} 天未签` }}
                    </span>
                  </div>
                  <!-- 漏签的主体是「某账号的某类任务」，同一账号寝/活两条都漏时若不带类型就是两张一样的卡片 -->
                  <p class="mt-1 flex items-center gap-1 pl-3.5 text-[11px] text-ink-muted">
                    <span class="min-w-0 truncate">{{ row.username || '未绑定用户' }}</span>
                    <span class="shrink-0">· {{ taskTypeMeta(row.taskType).label }}</span>
                  </p>
                  <!-- 严重度条：长度 = 未签天数 / 30，一眼比得出谁更久；从未签到取满格
                       ——它是质变（这条任务根本没跑通），不是「比 30 天还久」。 -->
                  <div class="mt-1 flex h-4 items-center pl-3.5">
                    <div class="h-[3px] w-full overflow-hidden rounded-full bg-ink/[0.07]">
                      <div
                        class="h-full rounded-full"
                        :class="row.days === null ? 'bg-danger' : 'bg-amber'"
                        :style="{ width: staleBarPct(row) + '%' }"
                      ></div>
                    </div>
                  </div>
                </li>
                <li v-if="!health.staleSign.list.length" class="rounded-lg bg-success/10 px-2.5 py-2 text-xs text-success">
                  无漏签风险任务
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <!-- ============ 推送送达（全站） ============
           口径说明必须写在卡里：成功率的分母只含「真实发出去的推送」（attempts>0），
           未发送（没配凭证/凭证缺字段）单列——不写清楚，管理员会把「用户没配凭证」
           读成「推送通道坏了」，这是这套统计最容易骗到人的地方。 -->
      <section class="dash-card p-5 sm:p-6 v-reveal delay-3">
        <div class="flex flex-wrap items-center justify-between gap-3 mb-5">
          <div>
            <h3 class="font-semibold text-ink">推送送达</h3>
            <p class="mt-0.5 text-xs text-ink-muted">
              近 {{ pushHealth.days }} 天 · 送达率只统计真实发出的推送，未发送单列、不计入分母
            </p>
          </div>
          <span
            class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
            :class="PUSH_TONE[pushTone].cls"
          >
            <span class="h-1.5 w-1.5 rounded-full" :class="PUSH_TONE[pushTone].dot"></span>
            {{ pushBadge }}
          </span>
        </div>

        <p v-if="pushEmpty" class="rounded-xl bg-cloud/60 px-3 py-6 text-center text-sm text-ink-muted">
          近 {{ pushHealth.days }} 天没有推送记录
        </p>

        <template v-else>
          <!-- 摘要 -->
          <div class="flex flex-wrap items-baseline gap-x-6 gap-y-2">
            <div>
              <span class="text-2xl font-bold tabular-nums text-ink">{{ pushHealth.summary.sent }}</span>
              <span class="ml-1 text-xs text-ink-muted">次真实发送</span>
            </div>
            <div>
              <span class="text-2xl font-bold tabular-nums" :class="rateTextCls(pushHealth.summary.rate)">
                {{ pushHealth.summary.rate === null ? '—' : pushHealth.summary.rate }}<span
                  v-if="pushHealth.summary.rate !== null" class="text-base">%</span>
              </span>
              <span class="ml-1 text-xs text-ink-muted">送达率</span>
            </div>
            <div class="text-xs text-ink-muted">
              成功 <span class="font-medium tabular-nums text-success">{{ pushHealth.summary.ok }}</span>
              · 失败 <span class="font-medium tabular-nums text-danger">{{ pushHealth.summary.fail }}</span>
              · 未发送 <span class="font-medium tabular-nums text-amber">{{ pushHealth.summary.skipped }}</span>
            </div>
          </div>

          <div class="mt-5 grid gap-6 lg:grid-cols-2">
            <!-- 左：按通道 -->
            <div class="min-w-0">
              <div class="mb-2 flex items-center justify-between gap-2">
                <p class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">按通道</p>
                <span class="text-[11px] text-ink-muted">{{ pushHealth.summary.channels }} 个通道有发送</span>
              </div>
              <ul class="space-y-1.5">
                <li
                  v-for="c in pushHealth.byChannel"
                  :key="'ch' + c.channel"
                  class="flex items-center gap-2.5 rounded-lg bg-cloud/70 px-2.5 py-2 text-xs"
                >
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
                <li v-if="!pushHealth.byChannel.length" class="rounded-lg bg-cloud/60 px-2.5 py-2 text-xs text-ink-muted">
                  没有通道产生过发送
                </li>
              </ul>
            </div>

            <!-- 右：签到成功但通知未送达（PushLog 建表动机里那次真实事故：签到页全是成功，
                 用户却从头到尾没收到通知）。真失败排在未发送之前——前者要查通道，后者要催配置。 -->
            <div class="min-w-0">
              <div class="mb-2 flex items-center justify-between gap-2">
                <p class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">签到成功但通知未送达</p>
                <span v-if="pushHealth.signOkPushFail.total > pushHealth.signOkPushFail.list.length" class="text-[11px] text-ink-muted">
                  共 {{ pushHealth.signOkPushFail.total }} 条
                </span>
              </div>
              <ul class="space-y-1.5">
                <li
                  v-for="x in pushHealth.signOkPushFail.list"
                  :key="'pf' + x.signRecordId + x.channel + x.time"
                  class="rounded-lg px-2.5 py-2 text-xs"
                  :class="x.skipped ? 'bg-amber/[0.08]' : 'bg-danger/[0.06]'"
                >
                  <div class="flex items-center gap-2">
                    <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="x.skipped ? 'bg-amber' : 'bg-danger'"></span>
                    <span class="min-w-0 flex-1 truncate font-medium text-ink">
                      {{ x.username || '未绑定用户' }}<template v-if="x.account"> · {{ x.account }}</template>
                    </span>
                    <span class="shrink-0 text-[11px] text-ink-muted tabular-nums">{{ x.time }}</span>
                  </div>
                  <!-- 原因文案可能很长（含 code/HTTP 状态），截断但保留 title 供悬停查看 -->
                  <p class="mt-1 truncate pl-3.5 text-[11px] text-ink-muted" :title="x.error">
                    <span class="font-medium" :class="x.skipped ? 'text-amber' : 'text-danger'">{{ x.skipped ? '未发送' : '发送失败' }}</span>
                    · {{ channelLabel(x.channel) }}<template v-if="x.error"> · {{ x.error }}</template>
                  </p>
                </li>
                <li v-if="!pushHealth.signOkPushFail.list.length" class="rounded-lg bg-success/10 px-2.5 py-2 text-xs text-success">
                  签到成功的通知全部送达
                </li>
              </ul>
            </div>
          </div>

          <!-- 失败/未发送原因归类：两组分开，跳过类混进失败组会让「没配凭证」看起来像通道故障 -->
          <div
            v-if="pushHealth.failReasons.length || pushHealth.skipReasons.length"
            class="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-ink/5 pt-3 text-[11px]"
          >
            <div v-if="pushHealth.failReasons.length" class="flex flex-wrap items-center gap-1.5">
              <span class="text-ink-muted">发送失败</span>
              <span v-for="r in pushHealth.failReasons" :key="'fr' + r.category" class="rounded-full bg-danger/10 px-2 py-0.5 text-danger">
                {{ r.category }} {{ r.count }}
              </span>
            </div>
            <div v-if="pushHealth.skipReasons.length" class="flex flex-wrap items-center gap-1.5">
              <span class="text-ink-muted">未发送（不计入送达率）</span>
              <span v-for="r in pushHealth.skipReasons" :key="'sr' + r.category" class="rounded-full bg-amber/15 px-2 py-0.5 text-amber">
                {{ r.category }} {{ r.count }}
              </span>
            </div>
          </div>
        </template>
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
              <thead class="sticky top-0 bg-elevated">
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
                class="h-8 w-full rounded-lg border border-ink/10 bg-elevated pl-8 pr-2 text-xs text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/10"
              />
            </div>
            <div class="w-32 sm:w-36">
              <BaseSelect v-model="fType" size="sm" :options="[{ label: '全部类型', value: 'all' }, { label: '寝室签到', value: 'dorm' }, { label: '活动签到', value: 'activity' }]" />
            </div>
          </div>
        </div>
        <!-- 容器高度 = 表头 41 + 行高 45 × 每页 10 条 = 491：一页正好一屏，翻页后不必再补滚 -->
        <div class="health-scroll overflow-y-auto lg:max-h-[491px]">
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
                  <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium" :class="taskTypeMeta(r.taskType).cls">
                    {{ taskTypeMeta(r.taskType).label }}
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
      <!-- 左列两张卡：调度器自身指标撑不满右卡高度，与其被拉伸留白，不如各表一件事
           ——运行现状 + 工作节奏，两卡合计自然接近右卡，不依赖任何硬撑 -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="flex flex-col gap-4">
          <section class="dash-card p-5 v-reveal delay-5">
            <div class="flex items-center justify-between mb-4">
              <h3 class="font-semibold text-ink">调度器运行状态</h3>
              <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium" :class="scheduler.running ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'">
                <span class="h-1.5 w-1.5 rounded-full" :class="scheduler.running ? 'bg-success animate-pulse' : 'bg-danger'"></span>
                {{ scheduler.running ? '运行中' : '已暂停' }}
              </span>
            </div>
            <dl class="space-y-2.5 text-sm">
              <div class="flex items-baseline justify-between gap-3">
                <dt class="shrink-0 text-ink-muted">启用任务</dt>
                <dd class="text-right font-medium text-ink tabular-nums">
                  {{ schedulesEnabled }} 个
                  <span class="ml-1 text-xs font-normal text-ink-muted">寝室 {{ taskTypes.dorm }} · 活动 {{ taskTypes.activity }}</span>
                </dd>
              </div>
              <div class="flex items-baseline justify-between gap-3">
                <dt class="shrink-0 text-ink-muted">已注册定时</dt>
                <dd class="text-right font-medium text-ink tabular-nums">
                  {{ scheduler.jobCount }} 个
                  <span v-if="unregisteredCount" class="ml-1 text-xs font-normal text-amber">未注册 {{ unregisteredCount }}</span>
                </dd>
              </div>
              <div class="flex items-baseline justify-between gap-3">
                <dt class="shrink-0 text-ink-muted">最近执行</dt>
                <dd class="font-medium text-ink" :title="scheduler.lastRunAt || '暂无执行记录'">{{ scheduler.lastRunAgo || '暂无记录' }}</dd>
              </div>
              <div class="flex items-baseline justify-between gap-3">
                <dt class="shrink-0 text-ink-muted">下次执行</dt>
                <dd class="text-right font-medium text-ink tabular-nums">
                  {{ nextRunText }}
                  <span v-if="nextInText" class="ml-1 text-xs font-normal text-ink-muted">{{ nextInText }}</span>
                </dd>
              </div>
            </dl>
          </section>

          <section class="dash-card p-5 v-reveal delay-5">
            <h3 class="font-semibold text-ink">调度节奏</h3>
            <p class="mt-0.5 mb-4 text-xs text-ink-muted">任务何时被触发、失败后多久补跑</p>
            <dl class="space-y-2.5 text-sm">
              <div class="flex items-center justify-between gap-3"><dt class="text-ink-muted">对账心跳</dt><dd class="font-medium text-ink tabular-nums">每 {{ rhythm.reconcileSeconds }} 秒</dd></div>
              <div class="flex items-center justify-between gap-3"><dt class="text-ink-muted">活动探测</dt><dd class="font-medium text-ink">随心跳轮询</dd></div>
              <div class="flex items-center justify-between gap-3"><dt class="text-ink-muted">失败补跑</dt><dd class="font-medium text-ink tabular-nums">{{ rhythm.retryDelayMinutes }} 分钟后</dd></div>
              <div class="flex items-center justify-between gap-3"><dt class="text-ink-muted">日志清理</dt><dd class="font-medium text-ink tabular-nums">每 {{ rhythm.pruneIntervalHours }} 小时</dd></div>
              <div class="flex items-center justify-between gap-3"><dt class="text-ink-muted">日志保留</dt><dd class="font-medium text-ink tabular-nums">{{ rhythm.logRetentionDays }} 天</dd></div>
            </dl>
          </section>
        </div>

        <section class="dash-card p-5 lg:col-span-2 v-reveal delay-5">
          <h3 class="font-semibold text-ink mb-4">即将执行的任务</h3>
          <ul class="space-y-2">
            <li v-for="(n, i) in scheduler.nextRuns" :key="i" class="flex items-start gap-3 rounded-xl border border-ink/5 bg-ink/[0.02] px-3 py-2.5 text-sm">
              <span class="inline-flex shrink-0 items-center rounded-full bg-brand/10 px-2.5 py-0.5 text-xs font-medium text-brand">{{ n.taskLabel }}</span>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="min-w-0 flex-1 truncate font-medium text-ink">{{ n.account }}</span>
                  <span class="shrink-0 text-xs text-ink-muted tabular-nums">{{ n.time }}</span>
                </div>
                <!-- 账号只说明「签哪个号」，用户与姓名说明「谁的任务」，缺一都定位不到人 -->
                <p class="mt-0.5 truncate text-xs text-ink-muted">
                  用户 {{ n.username || '—' }}<template v-if="n.studentName"> · 姓名 {{ n.studentName }}</template>
                </p>
              </div>
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
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { gsap } from 'gsap'
import { storeToRefs } from 'pinia'
import StatCard from '@/components/StatCard.vue'
import BaseChart from '@/components/BaseChart.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import Icon from '@/components/Icon.vue'
import { useAdminOverviewStore } from '@/stores/adminOverview'
import { useThemeStore, withAlpha } from '@/stores/theme'
import { taskTypeMeta } from '@/utils/accountType'
import { channelDot, channelLabel } from '@/utils/pushChannels'

// [权限判断] 本页仅管理员可达（分发见 DashboardView；路由守卫二次校验）。
const store = useAdminOverviewStore()
const { data: dash, loading, refreshing, loaded } = storeToRefs(store)
// 主题取色：额度分桶梯队等图表元素随主题联动（在 computed 内访问即自动重绘）
const themeStore = useThemeStore()

const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

// ===== 概览引用 =====
const summary = computed(() => dash.value.summary)
const quota = computed(() => dash.value.quota)
const scheduler = computed(() => dash.value.scheduler)
const health = computed(() => dash.value.accountHealth)
const riskUsers = computed(() => dash.value.riskUsers)

// ===== 推送送达 =====
// 接口缺字段时给空结构（后端未热重启时旧响应里没有该键），首帧渲染安全
const PUSH_EMPTY = {
  days: 7,
  summary: { sent: 0, ok: 0, fail: 0, skipped: 0, rate: null, channels: 0 },
  byChannel: [], failReasons: [], skipReasons: [],
  signOkPushFail: { total: 0, list: [] },
}
const pushHealth = computed(() => dash.value.pushHealth || PUSH_EMPTY)
const pushUndelivered = computed(() => pushHealth.value.summary.fail + pushHealth.value.summary.skipped)
const pushEmpty = computed(() => !pushHealth.value.summary.sent && !pushHealth.value.summary.skipped)
// 有真失败才算 danger；清一色「没发出去」是配置问题不是通道故障，用 amber 区分严重度
const pushTone = computed(() => {
  if (pushHealth.value.summary.fail > 0) return 'danger'
  if (pushUndelivered.value > 0) return 'amber'
  return 'success'
})
const PUSH_TONE = {
  success: { cls: 'bg-success/10 text-success', dot: 'bg-success' },
  amber: { cls: 'bg-amber/10 text-amber', dot: 'bg-amber' },
  danger: { cls: 'bg-danger/10 text-danger', dot: 'bg-danger animate-pulse' },
}
const pushBadge = computed(() => {
  const n = pushUndelivered.value
  if (!n) return '全部送达'
  return pushTone.value === 'danger' ? `${n} 条未送达` : `${n} 条未发送`
})
// 送达率分档：≥95 正常 / ≥80 留意 / 更低告警（无发送记录时不表态）
const rateTextCls = (r) => (r === null ? 'text-ink-muted' : r >= 95 ? 'text-success' : r >= 80 ? 'text-amber' : 'text-danger')
const rateBarCls = (r) => (r === null ? 'bg-ink/20' : r >= 95 ? 'bg-success' : r >= 80 ? 'bg-amber' : 'bg-danger')

// 日志区：store 未单出 recentLogs，从聚合数据派生并兜底空结构（首帧渲染安全）
const recentLogs = computed(() => dash.value.recentLogs || { items: [], total: 0, page: 1, page_size: 10 })
const schedulesEnabled = computed(() => dash.value.schedulesEnabled || 0)
// 页面根元素：健康卡 GSAP 的作用域（此前用文档级 '.health-row' 选择器，会误伤其它页面）
const pageRef = ref(null)

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
// 离开页面后防抖定时器不再触发无主的筛选请求
onUnmounted(() => clearTimeout(userTimer))

const logTotalPages = computed(() => Math.max(1, Math.ceil(recentLogs.value.total / (recentLogs.value.page_size || 10))))

// ===== 图表配色 =====
// 与 UserDashboard 同：ECharts 不认 CSS 变量，色值取 theme store 的 chart（读计算样式真值）。
// option 都是 computed，读写 CH.* 即建立依赖，切色相或切明暗后自动重算并重绘。
// 命名避开 C——本文件下面的 C 是圆环周长常量。
const CH = {
  get ink() { return themeStore.chart.ink },
  get grid() { return themeStore.chart.grid },
  get axis() { return themeStore.chart.axis },
  get ring() { return themeStore.chart.ring },
  get ringTrack() { return themeStore.chart.ringTrack },
  get border() { return themeStore.chart.border },
  get brand() { return themeStore.chart.brand },
  get brandLight() { return themeStore.chart.brandLight },
  get success() { return themeStore.chart.success },
  get warning() { return themeStore.chart.warning },
  get danger() { return themeStore.chart.danger },
  get neutral() { return themeStore.chart.neutral },
  get categorical() { return themeStore.chart.categorical },
}

// ===== 趋势图 =====
const trendSeries = computed(() => dash.value.trend[fRange.value] || [])
const trendOption = computed(() => ({
  grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
  tooltip: { trigger: 'axis' },
  legend: { data: ['成功', '失败', '跳过'], top: 0, textStyle: { color: CH.ink, fontSize: 11 } },
  xAxis: { type: 'category', boundaryGap: false, data: trendSeries.value.map((d) => d.date), axisLine: { lineStyle: { color: CH.axis } } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: CH.grid } } },
  series: [
    { name: '成功', type: 'line', smooth: true, symbolSize: 5, data: trendSeries.value.map((d) => d.success), itemStyle: { color: CH.success }, areaStyle: { color: withAlpha(CH.success, 0.08) } },
    { name: '失败', type: 'line', smooth: true, symbolSize: 5, data: trendSeries.value.map((d) => d.fail), itemStyle: { color: CH.danger } },
    { name: '跳过', type: 'line', smooth: true, symbolSize: 5, data: trendSeries.value.map((d) => d.skip), itemStyle: { color: CH.warning } },
  ],
}))

// ===== 失败原因分布（归类后） =====
const failTotal = computed(() => dash.value.failCategories.reduce((n, c) => n + c.count, 0))
const failOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} 次（{d}%）' },
  legend: { orient: 'vertical', right: 8, top: 'middle', textStyle: { color: CH.ink, fontSize: 11 } },
  series: [{
    type: 'pie', radius: ['48%', '72%'], center: ['36%', '50%'],
    itemStyle: { borderRadius: 6, borderColor: CH.border, borderWidth: 2 },
    label: { show: false },
    data: dash.value.failCategories.map((c, i) => ({ name: c.category, value: c.count, itemStyle: { color: CH.categorical[i % CH.categorical.length] } })),
  }],
}))

// ===== 额度健康分桶 =====
// 梯队中段两档（<50% / 50~79%）取当前主题 brand 的两档——额度充裕程度用
// 主题色深浅表达、随色相与明暗自动重绘；未使用/预警/已满保持中性档与语义色。
const quotaOption = computed(() => {
  const b = quota.value.buckets
  const data = [
    { name: '未使用', value: b.unused, itemStyle: { color: CH.neutral } },
    { name: '<50%', value: b.lt50, itemStyle: { color: CH.brandLight } },
    { name: '50~79%', value: b.r50to79, itemStyle: { color: CH.brand } },
    { name: '80~99%', value: b.r80to99, itemStyle: { color: CH.warning } },
    { name: '已满', value: b.full, itemStyle: { color: CH.danger } },
  ]
  return {
    grid: { left: 8, right: 16, top: 30, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis', formatter: '{b}: {c} 人' },
    xAxis: { type: 'category', data: data.map((d) => d.name), axisLine: { lineStyle: { color: CH.axis } } },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: CH.grid } } },
    series: [{ type: 'bar', barWidth: 36, data, label: { show: true, position: 'top', color: CH.ink } }],
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
// 待处理总数：右上徽标从「需要关注」升级为带计数（1 项与 50 项此前显示同一句话）
const riskTotal = computed(() => invalidTotal.value + staleTotal.value)
const hasRisk = computed(() => riskTotal.value > 0)

// 环与条的取色对齐语义色 token，并随明暗走（深色下语义色整体提亮），故取令牌真值
const ringOk = computed(() => CH.success)
const ringDanger = computed(() => CH.danger)
const ringAmber = computed(() => CH.warning)

// 环外发光随状态走：此前固定红色，账号全正常时绿环也发红光
function ringGlow(active, kind) {
  if (!active) return `drop-shadow(0 0 6px ${withAlpha(CH.success, 0.16)})`
  return kind === 'stale'
    ? `drop-shadow(0 0 6px ${withAlpha(CH.warning, 0.2)})`
    : `drop-shadow(0 0 6px ${withAlpha(CH.danger, 0.22)})`
}

// 漏签严重度条的量程：30 天记满格（更久也是满格）
const STALE_BAR_DAYS = 30

function staleBarPct(row) {
  if (row.days === null || row.days === undefined) return 100
  return Math.min(100, Math.round((row.days / STALE_BAR_DAYS) * 100))
}

const ringInvalid = ref(null)
const ringStale = ref(null)
const invalidNum = ref(0)
const staleNum = ref(0)
// 下次执行时间：调度器 nextRuns 的最早一条（cron 任务与轮询任务混合排序）
const nextRunText = computed(() => scheduler.value.nextRuns[0]?.time || '暂无排期')
// 距下次执行的相对时间：后端按请求时刻算好，页面不为此再挂定时器
const nextInText = computed(() => {
  const m = scheduler.value.nextRunIn
  if (m === null || m === undefined) return ''
  if (m < 1) return '不到 1 分钟后'
  if (m < 60) return `约 ${m} 分钟后`
  const h = Math.round(m / 60)
  return h < 24 ? `约 ${h} 小时后` : `约 ${Math.round(h / 24)} 天后`
})
// 类型构成与节奏参数：接口缺字段时给与后端一致的兜底，避免卡片出现空值
const taskTypes = computed(() => scheduler.value.taskTypes || { dorm: 0, activity: 0 })
const rhythm = computed(() => scheduler.value.rhythm || {
  reconcileSeconds: 30, pruneIntervalHours: 24, retryDelayMinutes: 10, logRetentionDays: 180,
})
// 启用任务里未注册 cron 的数量：活动 course 关每日兜底、或缺少有效时刻的任务属此类
const unregisteredCount = computed(() =>
  Math.max(0, schedulesEnabled.value - (scheduler.value.jobCount || 0)))

function animateHealth() {
  const setFinal = () => {
    if (ringInvalid.value) ringInvalid.value.style.strokeDashoffset = String(C * (1 - invalidRate.value))
    if (ringStale.value) ringStale.value.style.strokeDashoffset = String(C * (1 - staleRate.value))
    invalidNum.value = invalidTotal.value
    staleNum.value = staleTotal.value
  }
  if (prefersReduced) return setFinal()
  // kill 上一轮补间：两个 watch（数据变化/骨架结束）可能快速连续触发，
  // 旧补间不杀会与新补间同写圆环 offset 与数字 ref，出现数值来回跳
  if (healthTween) healthTween.kill()
  const t = { a: 0, b: 0, na: 0, nb: 0 }
  healthTween = gsap.to(t, {
    a: invalidRate.value, b: staleRate.value, na: invalidTotal.value, nb: staleTotal.value,
    duration: 1, ease: 'power2.out',
    onUpdate: () => {
      if (ringInvalid.value) ringInvalid.value.style.strokeDashoffset = String(C * (1 - t.a))
      if (ringStale.value) ringStale.value.style.strokeDashoffset = String(C * (1 - t.b))
      invalidNum.value = Math.round(t.na)
      staleNum.value = Math.round(t.nb)
    },
  })
  // 作用域限定在页面根元素内，避免文档级 '.health-row' 选择器误伤其它页面
  const rows = pageRef.value?.querySelectorAll('.health-row')
  if (rows?.length) {
    gsap.fromTo(rows, { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.35, stagger: 0.04, clearProps: 'opacity,transform' })
  }
}

let healthTween = null
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
