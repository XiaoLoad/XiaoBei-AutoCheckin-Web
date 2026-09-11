<template>
  <div class="flex flex-col gap-5 lg:flex-1">
    <!--
      重构要点（布局与信息架构）：
      1) 目录即层级：左栏「设置目录」按「账户 / 外观 / 系统运行 / 系统参数」四组列出锚点，
         组内可跳转、随滚动高亮、并标出哪一段存在未保存改动。层级只在这一处画一次，
         内容区不再重复"组头 + 卡头 + 子组头"三层标题。目录自身是一个轻面板（底色 + 发丝线、
         不加投影），比内容面板低一档：它只做轨道，不做主表面。
      2) 内容区是单一表面（dash-card + 发丝线分段），不再一模块一卡——
         避免多张等重视觉块堆叠导致层级扁平。
      3) 读数与设置靠形状区分，不靠标题：只读读数一律内嵌圆角块（账户信息=浅色、
         系统运行=深色面板），可写设置一律为"左说明 / 右控件"的行。一条规则贯穿全页。
      4) 签名：改动可见性主线——目录上的琥珀刻度 + 底部浮动保存条（可展开逐项 diff、
         支持单项撤销、保存后原地给回执）。改了什么、还没存，全页持续可见。
      5) 响应式：lg 起左目录常驻吸附，移动端降级为顶栏下方的横向 chip 轨（同样带高亮与脏点）。
      6) 权限：普通用户仅「账户 / 外观」两组，系统运行与系统参数不渲染（后端二次鉴权）。
    -->

    <!-- 页首导语：短竖线由 p 的 border-left 承担，盒模型保证与首行文字对齐 -->
    <p class="shrink-0 border-l-[3px] border-brand/60 pl-2.5 text-[13px] leading-relaxed text-ink-muted">
      按功能分组管理账户安全、界面外观与系统运行参数；改动会先在底部逐项列出，确认后一次性写入。
    </p>

    <!-- ===== 移动端目录：横向 chip 轨，吸附在顶栏（h-16）之下 ===== -->
    <nav
      class="sticky top-16 z-10 -mx-4 -my-1 bg-surface/95 px-4 py-1 backdrop-blur sm:-mx-6 sm:px-6 lg:hidden"
      aria-label="设置目录"
    >
      <div class="chip-scroll flex gap-1.5 overflow-x-auto py-1">
        <button
          v-for="s in allSections"
          :key="s.id"
          type="button"
          class="relative inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
          :class="activeSec === s.id ? 'bg-brand/10 text-brand' : 'text-ink-soft hover:bg-cloud'"
          :aria-current="activeSec === s.id ? 'true' : undefined"
          @click="goTo(s.id)"
        >
          {{ s.label }}
          <span v-if="dirtyBySection[s.id]" class="h-1.5 w-1.5 rounded-full bg-amber" aria-hidden="true"></span>
        </button>
      </div>
    </nav>

    <!-- ===== 两栏：左目录（lg 常驻吸附） + 右设置面板 =====
         容器刻意不定高、不设 min-h-0：左目录 sticky 的可用范围就是本容器的盒子，
         一旦容器被压到视口高度，目录滚过半屏就失去吸附；这里让容器随面板内容自然变高 -->
    <div class="flex flex-col gap-4 lg:flex-row lg:items-start">
      <!-- 左：设置目录。lg:self-start 是吸附生效的前提——grid/flex 项默认 stretch，拉伸后 sticky 不生效 -->
      <nav class="fade-up hidden shrink-0 lg:sticky lg:top-6 lg:block lg:w-[232px] lg:self-start" aria-label="设置目录">
        <!-- 目录自成一个轻面板：只有底色与发丝线、不加投影，比右面板低一档——
             既立住自己的边界，也不与内容区争「主表面」的身份 -->
        <div class="rounded-2xl border border-ink/5 bg-card/80 p-3">
          <p class="mb-3 px-2.5 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">设置目录</p>

          <!-- 导轨层：树线分别画在各组 <ul> 上（组标题因此能"断开"树线、读作标题），
               而定位标全目录只有一个，跨组靠 transform 滑动——不再逐项挂载/卸载，
               换段时不会出现刻度闪烁 -->
          <div ref="navRailRef" class="relative">
            <span
              class="pointer-events-none absolute left-[9.5px] top-0 h-[18px] w-[2px] rounded-full bg-brand transition-[transform,opacity] duration-200 ease-out"
              :style="markerStyle"
              aria-hidden="true"
            ></span>

            <div v-for="g in navGroups" :key="g.id" class="mb-4 last:mb-0">
              <p class="mb-1.5 flex items-center gap-2 px-2.5 text-[11px] font-semibold uppercase tracking-wider text-ink/40">
                {{ g.title }}
                <span
                  v-if="g.admin"
                  class="rounded bg-cloud px-1 py-px text-[10px] font-medium normal-case tracking-normal text-ink-muted"
                >仅管理员</span>
              </p>

              <!-- 树线连接「组 → 组内锚点」：选中态由导轨层上的定位标覆盖，与账号树同一套语汇 -->
              <ul class="ml-2.5 border-l border-ink/10 pl-3">
                <li v-for="s in g.items" :key="s.id">
                  <a
                    :href="'#sec-' + s.id"
                    :data-nav-id="s.id"
                    class="relative -ml-3 block rounded-lg py-1.5 pl-3 pr-7 text-[13px] leading-snug transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
                    :class="activeSec === s.id
                      ? 'font-semibold text-brand'
                      : 'text-ink-soft hover:bg-cloud/70 hover:text-ink'"
                    :aria-current="activeSec === s.id ? 'true' : undefined"
                    @click.prevent="goTo(s.id)"
                  >
                    {{ s.label }}
                    <span
                      v-if="dirtyBySection[s.id]"
                      class="absolute right-2.5 top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-amber"
                      aria-hidden="true"
                      title="该段有未保存的改动"
                    ></span>
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </nav>

      <!-- 右：设置面板（单一表面，发丝线分段） -->
      <div ref="panelRef" class="dash-card fade-up delay-1 min-w-0 lg:flex-1">
        <!-- ========== 账户信息（只读读数：浅色内嵌块） ========== -->
        <section
          id="sec-account-info"
          data-sec="account-info"
          class="scroll-mt-32 border-b border-ink/5 px-4 py-5 sm:px-6 sm:py-6 lg:scroll-mt-6"
          aria-labelledby="sec-hd-account-info"
        >
          <header class="mb-3 flex items-start gap-3">
            <span class="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand" aria-hidden="true">
              <Icon name="user" :size="15" />
            </span>
            <div class="min-w-0">
              <h3 id="sec-hd-account-info" class="text-sm font-semibold text-ink">账户信息</h3>
              <p class="mt-0.5 text-xs leading-relaxed text-ink-muted">当前登录身份与用量基线，由系统记录，不可在此修改</p>
            </div>
          </header>

          <!-- 读数块：浅色内嵌，与下方"设置行"在形状上区分开 -->
          <div class="rounded-xl bg-cloud/60 p-4 ring-1 ring-inset ring-ink/5">
            <!-- 骨架：与「身份区 + 三列体征」最终几何同构 -->
            <div v-if="meLoading" class="flex flex-col gap-5 xl:flex-row xl:items-center">
              <div class="flex shrink-0 items-center gap-3.5">
                <div class="h-12 w-12 rounded-full bg-ink/5 animate-pulse" />
                <div class="space-y-2">
                  <div class="h-4 w-24 rounded bg-ink/5 animate-pulse" />
                  <div class="h-3 w-14 rounded bg-ink/5 animate-pulse" />
                </div>
              </div>
              <div class="grid flex-1 gap-4 sm:grid-cols-3 xl:border-l xl:border-ink/5 xl:pl-6">
                <div v-for="i in 3" :key="i" class="space-y-2">
                  <div class="h-2.5 w-14 rounded bg-ink/5 animate-pulse" />
                  <div class="h-4 w-24 rounded bg-ink/5 animate-pulse" />
                </div>
              </div>
            </div>

            <div v-else class="flex flex-col gap-5 xl:flex-row xl:items-center">
              <div class="flex shrink-0 items-center gap-3.5">
                <span class="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-brand/15 text-lg font-semibold text-brand ring-1 ring-brand/20">
                  {{ (meInfo?.username || 'U').charAt(0).toUpperCase() }}
                </span>
                <div class="min-w-0">
                  <p class="truncate text-base font-semibold text-ink">{{ meInfo?.username || '-' }}</p>
                  <span class="mt-1 inline-flex items-center rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-medium text-brand">
                    {{ meRoleLabel }}
                  </span>
                </div>
              </div>

              <dl class="grid flex-1 gap-x-6 gap-y-4 sm:grid-cols-3 xl:border-l xl:border-ink/5 xl:pl-6">
                <div>
                  <dt class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">注册时间</dt>
                  <dd class="mt-1 text-sm font-semibold tabular-nums text-ink">{{ meInfo?.createdAt || '-' }}</dd>
                </div>
                <div>
                  <dt class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">最近登录</dt>
                  <dd class="mt-1 text-sm font-semibold tabular-nums text-ink">{{ meInfo?.lastLogin || '-' }}</dd>
                </div>
                <div>
                  <dt class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">额度使用</dt>
                  <dd class="mt-1 text-sm font-semibold tabular-nums text-ink">
                    {{ meInfo?.quota?.used ?? '-' }}
                    <span class="text-xs font-normal text-ink-muted">/ {{ meInfo?.quota?.limit ?? '-' }} 个平台账号</span>
                  </dd>
                  <!-- 额度条：<80% 品牌色、≥80% 琥珀（对齐 quota_warn_ratio 默认阈值）、满额危险红 -->
                  <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-ink/10">
                    <div
                      ref="quotaBarRef"
                      class="h-full origin-left rounded-full"
                      :class="quotaBarCls"
                      :style="{ width: quotaPct + '%' }"
                    />
                  </div>
                </div>
              </dl>
            </div>
          </div>
        </section>

        <!-- ========== 修改密码（设置：表单三列，动作右置） ========== -->
        <section
          id="sec-password"
          data-sec="password"
          class="scroll-mt-32 border-b border-ink/5 px-4 py-5 sm:px-6 sm:py-6 lg:scroll-mt-6"
          aria-labelledby="sec-hd-password"
        >
          <header class="mb-3 flex items-start gap-3">
            <span class="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand" aria-hidden="true">
              <Icon name="lock" :size="15" />
            </span>
            <div class="min-w-0">
              <h3 id="sec-hd-password" class="text-sm font-semibold text-ink">修改密码</h3>
              <p class="mt-0.5 text-xs leading-relaxed text-ink-muted">修改后当前会话立即失效，需要用新密码重新登录</p>
            </div>
          </header>

          <form ref="pwdCardRef" @submit.prevent="onChangePassword">
            <div class="grid gap-3 sm:grid-cols-3">
              <div>
                <label class="mb-1 block text-xs font-medium text-ink-muted" for="pwd-old">原密码</label>
                <input
                  id="pwd-old"
                  v-model="pwdForm.old"
                  type="password"
                  autocomplete="current-password"
                  placeholder="输入当前密码"
                  class="login-input px-3 py-2.5 text-sm"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs font-medium text-ink-muted" for="pwd-next">新密码</label>
                <input
                  id="pwd-next"
                  v-model="pwdForm.next"
                  type="password"
                  autocomplete="new-password"
                  :placeholder="pwdMinHint"
                  class="login-input px-3 py-2.5 text-sm"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs font-medium text-ink-muted" for="pwd-confirm">确认新密码</label>
                <input
                  id="pwd-confirm"
                  v-model="pwdForm.confirm"
                  type="password"
                  autocomplete="new-password"
                  placeholder="再次输入新密码"
                  class="login-input px-3 py-2.5 text-sm"
                  :class="confirmError && 'border-danger focus:border-danger focus:ring-danger/10'"
                />
                <p v-if="confirmError" class="mt-1 text-xs text-danger">{{ confirmError }}</p>
              </div>
            </div>

            <div class="mt-4 flex justify-end">
              <button
                type="submit"
                class="rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
                :disabled="pwdSubmitting || !pwdForm.old || !pwdForm.next || !pwdForm.confirm"
              >
                {{ pwdSubmitting ? '提交中…' : '修改密码' }}
              </button>
            </div>
          </form>
        </section>

        <!-- ========== 主题色（设置：平铺色板） ========== -->
        <section
          id="sec-theme"
          data-sec="theme"
          class="scroll-mt-32 border-b border-ink/5 px-4 py-5 sm:px-6 sm:py-6 lg:scroll-mt-6"
          aria-labelledby="sec-hd-theme"
        >
          <header class="mb-3 flex items-start gap-3">
            <span class="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand" aria-hidden="true">
              <Icon name="droplet" :size="15" />
            </span>
            <div class="min-w-0">
              <h3 id="sec-hd-theme" class="text-sm font-semibold text-ink">主题色</h3>
              <p class="mt-0.5 text-xs leading-relaxed text-ink-muted">一键切换全站品牌色，即时生效；仅记忆在当前浏览器</p>
            </div>
          </header>

          <div class="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6" role="radiogroup" aria-label="选择主题色">
            <button
              v-for="t in themePalette"
              :key="t.id"
              type="button"
              role="radio"
              :aria-checked="themeStore.current === t.id"
              class="flex items-center gap-2 rounded-xl border px-3 py-2.5 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
              :class="themeStore.current === t.id
                ? 'border-brand/40 bg-brand/5 ring-1 ring-brand/15'
                : 'border-ink/10 bg-white hover:border-ink/20 hover:bg-cloud/60'"
              @click="onPickTheme(t, $event)"
            >
              <span
                class="h-4 w-4 shrink-0 rounded-full ring-1 ring-inset ring-ink/10"
                :style="{ backgroundColor: t.brand }"
              ></span>
              <span class="min-w-0 flex-1 truncate text-left text-xs font-medium" :class="themeStore.current === t.id ? 'text-ink' : 'text-ink-soft'">{{ t.label }}</span>
              <Icon v-if="themeStore.current === t.id" name="check" :size="13" class="shrink-0 text-brand" />
            </button>
          </div>
        </section>

        <!-- ========== 系统运行（只读读数：深色内嵌块，仅管理员） ========== -->
        <section
          v-if="auth.isAdmin"
          id="sec-sysinfo"
          data-sec="sysinfo"
          class="scroll-mt-32 border-b border-ink/5 px-4 py-5 sm:px-6 sm:py-6 lg:scroll-mt-6"
          aria-labelledby="sec-hd-sysinfo"
        >
          <header class="mb-3 flex items-start gap-3">
            <span class="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand" aria-hidden="true">
              <Icon name="globe" :size="15" />
            </span>
            <div class="min-w-0">
              <h3 id="sec-hd-sysinfo" class="text-sm font-semibold text-ink">运行状态</h3>
              <p class="mt-0.5 text-xs leading-relaxed text-ink-muted">当前实例的版本、环境与运行读数</p>
            </div>
            <button
              type="button"
              class="ml-auto inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-ink-muted transition hover:bg-cloud hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
              @click="loadSystemInfo"
            >
              <Icon name="refresh" :size="13" :class="infoLoading && 'animate-spin'" />
              刷新
            </button>
          </header>

          <!-- 深色面板读数：全页唯一的身份色块，作为"环境读数"的视觉锚点 -->
          <div class="rounded-xl bg-panel p-4 ring-1 ring-white/10 sm:p-5">
            <!-- 骨架：与「版本主值区 + 三列体征」最终几何同构 -->
            <div v-if="infoLoading" class="flex flex-col gap-5 lg:flex-row lg:items-center">
              <div class="shrink-0 space-y-2.5">
                <div class="h-2.5 w-16 rounded bg-white/15 animate-pulse" />
                <div class="h-7 w-32 rounded bg-white/15 animate-pulse" />
                <div class="h-6 w-24 rounded-full bg-white/10 animate-pulse" />
              </div>
              <div class="grid flex-1 gap-4 sm:grid-cols-3 lg:border-l lg:border-white/10 lg:pl-6">
                <div v-for="i in 3" :key="i" class="space-y-2">
                  <div class="h-2.5 w-14 rounded bg-white/15 animate-pulse" />
                  <div class="h-4 w-20 rounded bg-white/15 animate-pulse" />
                </div>
              </div>
            </div>

            <div v-else class="flex flex-col gap-5 lg:flex-row lg:items-center">
              <!-- 版本是唯一主值：等宽字体强化工程感 -->
              <div class="shrink-0">
                <p class="text-[11px] font-semibold uppercase tracking-wider text-white/50">系统版本</p>
                <p ref="versionRef" class="mt-2 font-mono text-[26px] font-semibold leading-none tracking-tight text-white">v{{ sysInfo?.version ?? '-' }}</p>
                <span class="mt-3 inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium text-white/85 ring-1 ring-white/20">
                  <span class="h-1.5 w-1.5 rounded-full" :class="envDotCls"></span>
                  {{ envLabel }}
                </span>
              </div>

              <dl class="grid flex-1 gap-x-6 gap-y-4 sm:grid-cols-3 lg:border-l lg:border-white/10 lg:pl-6">
                <div>
                  <dt class="text-[11px] font-semibold uppercase tracking-wider text-white/50">数据库</dt>
                  <dd class="mt-1 flex items-center gap-2 text-sm font-semibold tabular-nums text-white">
                    <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="dbOk ? 'bg-success brand-dot' : 'bg-danger'"></span>
                    {{ dbOk ? '连接正常' : '连接异常' }}
                  </dd>
                </div>
                <div>
                  <dt class="text-[11px] font-semibold uppercase tracking-wider text-white/50">已运行时长</dt>
                  <dd class="mt-1 text-sm font-semibold tabular-nums text-white">{{ uptimeLabel }}</dd>
                  <p v-if="startedAtLabel" class="mt-0.5 text-xs text-white/45">{{ startedAtLabel }}</p>
                </div>
                <div>
                  <dt class="text-[11px] font-semibold uppercase tracking-wider text-white/50">用户规模</dt>
                  <dd class="mt-1 text-sm font-semibold tabular-nums text-white">{{ usersTotal }} 人</dd>
                  <p class="mt-0.5 text-xs text-white/45">管理员 {{ sysInfo?.users?.admins ?? '-' }} · 用户 {{ sysInfo?.users?.users ?? '-' }}</p>
                </div>
              </dl>
            </div>
          </div>
        </section>

        <!-- ========== 系统参数（仅管理员）：每组一段，行式排布；
             加载中以同构骨架占位，段头直接用注册表文案，目录与段落在数据到达前后不跳动 ========== -->
        <section
          v-for="g in displayGroups"
          :key="g.id"
          :id="'sec-' + g.id"
          :data-sec="g.id"
          class="scroll-mt-32 border-b border-ink/5 px-4 py-5 last:border-b-0 sm:px-6 sm:py-6 lg:scroll-mt-6"
          :aria-labelledby="'sec-hd-' + g.id"
        >
          <header class="mb-2 flex items-start gap-3">
            <span class="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand" aria-hidden="true">
              <Icon :name="g.icon" :size="15" />
            </span>
            <div class="min-w-0">
              <h3 :id="'sec-hd-' + g.id" class="text-sm font-semibold text-ink">{{ g.title }}</h3>
              <p class="mt-0.5 text-xs leading-relaxed text-ink-muted">{{ g.hint }}</p>
            </div>
          </header>

          <!-- 加载骨架：与设置行的最终几何同构 -->
          <template v-if="g.skeleton">
            <div v-for="i in 2" :key="i" class="param-row flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
              <div class="space-y-1.5">
                <div class="h-3.5 w-28 rounded bg-ink/5 animate-pulse" />
                <div class="h-3 w-48 rounded bg-ink/5 animate-pulse" />
              </div>
              <div class="h-9 w-24 shrink-0 rounded-lg bg-ink/5 animate-pulse" />
            </div>
          </template>

          <!-- 设置行：左说明 / 右控件。控件一律右置，形状按值类型收敛为三种 -->
          <div v-else>
            <div
              v-for="item in g.items"
              :key="item.key"
              class="param-row flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6"
            >
              <div class="min-w-0">
                <label :for="'param-' + item.key" class="flex flex-wrap items-center gap-1.5 text-sm font-medium text-ink">
                  {{ item.label }}
                  <span
                    v-if="isDirty(item)"
                    class="h-1.5 w-1.5 shrink-0 rounded-full bg-amber"
                    aria-hidden="true"
                    title="已修改，待保存"
                  ></span>
                  <span v-if="item.type === 'int'" class="text-[11px] font-normal tabular-nums text-ink/40">
                    {{ item.min }} ~ {{ item.max }}
                  </span>
                </label>
                <p class="mt-0.5 text-xs leading-relaxed text-ink-muted">{{ item.desc }}</p>
              </div>

              <ConfigToggle
                v-if="item.type === 'bool'"
                :id="'param-' + item.key"
                v-model="form[item.key]"
                class="shrink-0"
              />
              <input
                v-else-if="item.type === 'str'"
                :id="'param-' + item.key"
                v-model.trim="form[item.key]"
                type="text"
                autocomplete="off"
                class="login-input w-full shrink-0 px-3 py-2 text-sm sm:w-[300px]"
                placeholder="未配置"
              />
              <div v-else class="relative shrink-0">
                <input
                  :id="'param-' + item.key"
                  v-model.number="form[item.key]"
                  type="number"
                  :min="item.min"
                  :max="item.max"
                  class="login-input w-full px-3 py-2 pr-12 text-right text-sm tabular-nums sm:w-32"
                />
                <span class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-ink-muted">
                  {{ paramUnits[item.key] || '' }}
                </span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- ===== 浮动保存条：改动的唯一出口，也只在有改动时出现 =====
         sticky bottom 而非 fixed：lg 下随 main 的滚动视口、移动端随文档滚动，两端都成立；
         它在正常流中占位（末尾没有别的正文被压住），滚动中悬浮于内容之上，随滚动到末尾自然归位。
         mb-3 让"贴底"留出一致的气口——sticky 按外边距盒对齐，滚动中与滚到底都停在同一高度 -->
    <Transition name="savebar">
      <div v-if="barVisible" class="sticky bottom-0 z-20 mb-3">
        <div class="rounded-2xl bg-card px-4 py-3 ring-1 ring-ink/5 shadow-[0_1px_2px_rgba(20,33,61,0.04),0_18px_40px_-20px_rgba(20,33,61,0.35)]">
          <!-- 保存回执：原地切换，确认"这次点击生效了" -->
          <div v-if="showReceipt" ref="receiptRef" class="flex items-center gap-2.5">
            <span class="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-success-soft text-success" aria-hidden="true">
              <Icon name="check" :size="15" />
            </span>
            <div class="min-w-0">
              <p class="text-sm font-semibold text-ink">设置已保存</p>
              <p class="text-xs text-ink-muted">改动已写入，即时生效</p>
            </div>
          </div>

          <template v-else>
            <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
              <button
                type="button"
                class="inline-flex items-center gap-2 rounded-full bg-warning-soft px-2.5 py-1 text-xs font-medium text-warning transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warning/40"
                :aria-expanded="barOpen"
                aria-controls="savebar-diff"
                @click="barOpen = !barOpen"
              >
                <span class="h-1.5 w-1.5 rounded-full bg-warning" aria-hidden="true"></span>
                已修改 {{ changedCount }} 项
                <Icon name="chevron-down" :size="13" class="transition-transform" :class="barOpen && 'rotate-180'" />
              </button>

              <button
                type="button"
                class="text-xs font-medium text-ink-muted transition hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
                @click="discardAll"
              >
                放弃改动
              </button>

              <button
                type="button"
                :disabled="saving"
                class="ml-auto inline-flex items-center gap-1.5 rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
                @click="onSaveSettings"
              >
                {{ saving ? '保存中…' : '保存设置' }}
              </button>
            </div>

            <!-- 展开后逐项列出「原值 → 新值」，可单独撤销——提交前先看清自己改了什么 -->
            <div v-if="barOpen" id="savebar-diff" class="mt-3 border-t border-ink/5 pt-3">
              <ul class="space-y-0.5">
                <li
                  v-for="c in changedList"
                  :key="c.key"
                  class="flex items-center gap-3 rounded-lg px-1 py-1 text-xs"
                >
                  <span class="min-w-0 flex-1 truncate font-medium text-ink">{{ c.label }}</span>
                  <span class="shrink-0 tabular-nums text-ink-muted line-through">{{ c.fromText }}</span>
                  <Icon name="chevron-right" :size="12" class="shrink-0 text-ink/25" aria-hidden="true" />
                  <span class="shrink-0 font-semibold tabular-nums text-ink">{{ c.toText }}</span>
                  <button
                    type="button"
                    class="shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-medium text-ink-muted transition hover:bg-cloud hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
                    @click="undoOne(c.key)"
                  >
                    撤销
                  </button>
                </li>
              </ul>
              <div class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-ink/5 pt-2.5">
                <button
                  type="button"
                  class="text-xs font-medium text-ink-muted transition hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
                  @click="resetFormToDefaults"
                >
                  恢复出厂默认值
                </button>
                <span class="text-[11px] text-ink-muted">仅提交发生变化的项；会话时长对下一次登录生效</span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </Transition>

    <!-- 底部间距占位：真实在流子元素，盒高计入 scrollHeight，不受滚动容器末端 padding/margin 折叠影响；
         -mt-5 抵消根容器 gap-5，确保底部间距精确 24px、与其它页面一致 -->
    <div class="h-6 shrink-0 -mt-5" aria-hidden="true"></div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'
import ConfigToggle from '@/components/signconfig/ConfigToggle.vue'
import * as authApi from '@/api/auth'
import { fetchAccountInfo } from '@/api/me'
import { getSettings, updateSettings, getSystemInfo } from '@/api/settings'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { THEME_PALETTE as themePalette } from '@/config/themePalette'
import { toast } from '@/utils/toast'

const auth = useAuthStore()

// 细节动效统一开关：系统级减弱动效偏好下，GSAP 与平滑滚动全部短路
const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches

// ==================== 目录与滚动高亮 ====================
const panelRef = ref(null)
const navRailRef = ref(null)
const activeSec = ref('account-info')
const spyHits = new Set()
let spy = null

// 定位标：高度固定（动效只走 transform），纵向位置从当前锚点量出。
// 唯一写入点是 measureMarker——模板里不再按项渲染刻度，换段时没有挂载/卸载这一步。
const MARKER_H = 18
const markerY = ref(0)
const markerOn = ref(false)
const markerStyle = computed(() => ({
  transform: 'translateY(' + markerY.value + 'px)',
  opacity: markerOn.value ? 1 : 0,
}))

// 目录在移动端是 display:none，量到的高度恒为 0，此时藏起定位标（移动端用 chip 轨高亮）
function measureMarker() {
  const rail = navRailRef.value
  if (!rail) return
  const el = rail.querySelector('[data-nav-id="' + activeSec.value + '"]')
  if (!el || !el.offsetHeight) {
    markerOn.value = false
    return
  }
  markerY.value = el.offsetTop + (el.offsetHeight - MARKER_H) / 2
  markerOn.value = true
}

// 层级只在目录里画一次：四个组，组内挂锚点；系统运行/系统参数两组仅管理员可见
const navGroups = computed(() => {
  const groups = [
    {
      id: 'account',
      title: '账户',
      items: [
        { id: 'account-info', label: '账户信息' },
        { id: 'password', label: '修改密码' },
      ],
    },
    { id: 'appearance', title: '外观', items: [{ id: 'theme', label: '主题色' }] },
  ]
  if (auth.isAdmin) {
    groups.push({ id: 'runtime', title: '系统运行', admin: true, items: [{ id: 'sysinfo', label: '运行状态' }] })
    // 加载用例沿用注册表分组，目录不至于在数据到达前后跳动
    const params = settingsLoading.value ? PARAM_GROUPS : paramGroups.value
    if (params.length) {
      groups.push({
        id: 'params',
        title: '系统参数',
        admin: true,
        items: params.map((g) => ({ id: g.id, label: g.title })),
      })
    }
  }
  return groups
})

const allSections = computed(() => navGroups.value.flatMap((g) => g.items))

// 每段是否存在未保存改动：驱动目录上的琥珀刻度
const dirtyBySection = computed(() => {
  const map = {}
  for (const g of paramGroups.value) {
    map[g.id] = g.items.some((it) => isDirty(it))
  }
  return map
})

function goTo(id) {
  const el = document.getElementById('sec-' + id)
  if (!el) return
  activeSec.value = id
  el.scrollIntoView({ behavior: REDUCED_MOTION ? 'auto' : 'smooth', block: 'start' })
}

// 高亮取「落点带内 DOM 序最靠前的一段」：root 用视口，嵌套滚动容器（lg 下 main 自身滚动、
// 移动端文档滚动）由 IntersectionObserver 连同裁剪祖先一并计算，两种断点都成立。
function setupSpy() {
  spy?.disconnect()
  spy = null
  spyHits.clear()
  const els = panelRef.value ? Array.from(panelRef.value.querySelectorAll('[data-sec]')) : []
  if (!els.length) return
  spy = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        const id = e.target.dataset.sec
        if (e.isIntersecting) spyHits.add(id)
        else spyHits.delete(id)
      }
      const first = allSections.value.find((s) => spyHits.has(s.id))
      if (first) activeSec.value = first.id
    },
    { root: null, rootMargin: '-104px 0px -55% 0px', threshold: 0 }
  )
  els.forEach((el) => spy.observe(el))
}

// 定位标的几何重算见下方「段落集合变化」处——watch 注册时就会求一次旧值，
// 放这里会提前求值 navGroups（其依赖 settingsLoading/PARAM_GROUPS 尚未初始化，触发 TDZ）

// ==================== 区零：主题色（所有角色） ====================
const themeStore = useThemeStore()

function onPickTheme(t, e) {
  if (themeStore.current === t.id) return
  themeStore.setTheme(t.id)
  if (!REDUCED_MOTION && e?.currentTarget) {
    gsap.fromTo(
      e.currentTarget,
      { scale: 0.95 },
      { scale: 1, duration: 0.3, ease: 'back.out(2)', clearProps: 'transform' }
    )
  }
}

// ==================== 区一：修改密码 ====================
const pwdForm = reactive({ old: '', next: '', confirm: '' })
const pwdSubmitting = ref(false)
const confirmError = ref('')
const pwdCardRef = ref(null)
// 普通用户无权限读取系统参数，仅展示通用建议；精确下限由后端校验并在报错中返回
const minPwdLength = computed(() => {
  const item = settingsItems.value.find((it) => it.key === 'password_min_length')
  return item ? Number(item.current) : 0
})
const pwdMinHint = computed(() =>
  minPwdLength.value
    ? '至少 ' + minPwdLength.value + ' 位，建议混合字母与数字'
    : '建议 8 位以上并混合字母与数字'
)

async function onChangePassword() {
  confirmError.value = ''
  if (pwdForm.next !== pwdForm.confirm) {
    confirmError.value = '两次输入的新密码不一致'
    return
  }
  pwdSubmitting.value = true
  try {
    await authApi.changePassword({ old_password: pwdForm.old, new_password: pwdForm.next })
    toast('密码修改成功', 'success')
    pwdForm.old = ''
    pwdForm.next = ''
    pwdForm.confirm = ''
  } catch {
    /* 失败已由 request.js 全局 toast 提示 */
  } finally {
    pwdSubmitting.value = false
  }
}

// 校验失败抖动：动效指向出错位置，而不是只靠一行文案
watch(confirmError, (msg) => {
  if (!msg || REDUCED_MOTION || !pwdCardRef.value) return
  gsap.to(pwdCardRef.value, {
    keyframes: { x: [-5, 5, -3, 3, 0] },
    duration: 0.32,
    ease: 'power2.out',
    clearProps: 'x',
  })
})

// ==================== 区二：账户信息（所有角色，只读） ====================
const meInfo = ref(null)
const meLoading = ref(false)
const meRoleLabel = computed(() => (meInfo.value?.role === 'admin' ? '管理员' : '普通用户'))
// 宽度钳制在 0~100，防止后端异常值把轨道撑破
const quotaPct = computed(() => Math.min(100, Math.max(0, Number(meInfo.value?.quota?.pct ?? 0))))
// 额度条语义色：<80% 品牌色、≥80% 琥珀预警（对齐 quota_warn_ratio 默认阈值）、满额危险红
const quotaBarCls = computed(() => {
  if (quotaPct.value >= 100) return 'bg-danger'
  if (quotaPct.value >= 80) return 'bg-amber'
  return 'bg-brand'
})
const quotaBarRef = ref(null)

// 额度条数据到达后从 0 展开（scaleX 不与 width 绑定冲突），结束清内联变换交还响应式
watch(quotaPct, () => {
  if (REDUCED_MOTION || !quotaBarRef.value) return
  gsap.fromTo(
    quotaBarRef.value,
    { scaleX: 0 },
    { scaleX: 1, duration: 0.7, ease: 'power3.out', clearProps: 'transform' }
  )
})

async function loadAccountInfo() {
  meLoading.value = true
  try {
    meInfo.value = await fetchAccountInfo()
  } catch {
    /* 失败已由 request.js 全局 toast 提示；体征位以「-」占位 */
  } finally {
    meLoading.value = false
  }
}

// ==================== 区三：系统参数（仅管理员） ====================
const settingsItems = ref([])
const form = reactive({})
const defaultsSnapshot = reactive({})
const settingsLoading = ref(false)
const saving = ref(false)
const receiptRef = ref(null)
const savedFlash = ref(false)
const barOpen = ref(false)
let savedFlashTimer = null

// 分组目录：按业务语义归类，key → 组映射；后端新增未收录的键兜底进「其他参数」
const PARAM_GROUPS = [
  { id: 'register', title: '注册与额度', icon: 'user-check', hint: '新账号的开通方式与用量基线', keys: ['registration_enabled', 'default_quota'] },
  { id: 'security', title: '账号安全', icon: 'shield', hint: '密码策略与会话凭证有效期', keys: ['password_min_length', 'session_hours'] },
  { id: 'data', title: '数据治理', icon: 'layers', hint: '日志清理周期与预警口径', keys: ['sign_log_retention_days', 'quota_warn_ratio'] },
  { id: 'map', title: '地图服务', icon: 'map-pin', hint: '位置池「地图拾取」使用的高德开放平台凭证', keys: ['amap_web_key', 'amap_security_code'] },
]
// 数字参数的单位后缀：随输入框内联展示，免去把单位写进 label
const PARAM_UNITS = {
  default_quota: '个',
  password_min_length: '位',
  session_hours: '小时',
  sign_log_retention_days: '天',
  quota_warn_ratio: '%',
}

const paramUnits = PARAM_UNITS

const paramGroups = computed(() => {
  const byKey = Object.fromEntries(settingsItems.value.map((it) => [it.key, it]))
  const used = new Set()
  const groups = []
  for (const g of PARAM_GROUPS) {
    const items = g.keys.filter((k) => byKey[k]).map((k) => {
      used.add(k)
      return byKey[k]
    })
    if (items.length) groups.push({ ...g, items })
  }
  const rest = settingsItems.value.filter((it) => !used.has(it.key))
  if (rest.length) {
    groups.push({ id: 'other', title: '其他参数', icon: 'sliders', hint: '未归类的系统配置', items: rest })
  }
  return groups
})

// 参数区的渲染分组：加载中用注册表分组占位（段头为真实文案、正文为骨架），
// 到达后换为真实分组。两者 id 一致，目录与滚动锚点在加载前后保持稳定。
const displayGroups = computed(() => {
  if (!auth.isAdmin) return []
  if (settingsLoading.value) return PARAM_GROUPS.map((g) => ({ ...g, items: [], skeleton: true }))
  return paramGroups.value
})

function isDirty(item) {
  return form[item.key] !== undefined && form[item.key] !== item.current
}

const changedCount = computed(() => settingsItems.value.filter((it) => isDirty(it)).length)

// 值展示：bool 说人话，数字带单位，空值明确说「空」而不是留白
function fmtVal(item, value) {
  if (item.type === 'bool') return value ? '开启' : '关闭'
  if (value === '' || value === null || value === undefined) return '空'
  return `${value}${PARAM_UNITS[item.key] || ''}`
}

// 改动清单：保存前的逐项 diff，是浮动条展开后的内容
const changedList = computed(() =>
  settingsItems.value
    .filter((it) => isDirty(it))
    .map((it) => ({
      key: it.key,
      label: it.label,
      fromText: fmtVal(it, it.current),
      toText: fmtVal(it, form[it.key]),
    }))
)

// 保存后改动清零，但保存条要留一会儿给回执——故可见性取并集；
// 回执只在"确实没有待保存改动"时展示，避免边保存边改时显示已保存
const barVisible = computed(() => changedCount.value > 0 || savedFlash.value)
const showReceipt = computed(() => savedFlash.value && changedCount.value === 0)

function applyItems(items) {
  settingsItems.value = items || []
  for (const item of settingsItems.value) {
    form[item.key] = item.current
    defaultsSnapshot[item.key] = item.default
  }
}

async function loadSettings() {
  settingsLoading.value = true
  try {
    const data = await getSettings()
    applyItems(data.items)
  } catch {
    /* 失败已由 request.js 全局 toast 提示 */
  } finally {
    settingsLoading.value = false
  }
}

// 参数行数据到达后错落入场：仅在首次加载完成时触发一次
watch(settingsLoading, async (loading) => {
  if (loading || REDUCED_MOTION || !settingsItems.value.length) return
  await nextTick()
  const rows = panelRef.value?.querySelectorAll('.param-row')
  if (rows?.length) {
    gsap.fromTo(
      rows,
      { opacity: 0, y: 6 },
      { opacity: 1, y: 0, duration: 0.32, ease: 'power2.out', stagger: 0.02, clearProps: 'opacity,transform' }
    )
  }
})

// 段落集合随加载态/角色变化而增删，观察目标需同步重建
watch([settingsLoading, () => auth.isAdmin], async () => {
  await nextTick()
  setupSpy()
})

// 高亮变化、以及目录项增删（加载态与角色切换都会改动 navGroups）都会改变锚点几何，重新量一次定位标。
// 必须写在 settingsLoading/PARAM_GROUPS/paramGroups 之后：watch 注册时即求一次旧值，提前会触发 TDZ
watch([activeSec, navGroups], () => nextTick(measureMarker))

function resetFormToDefaults() {
  for (const item of settingsItems.value) {
    form[item.key] = defaultsSnapshot[item.key]
  }
}

// 单项撤销：把该键退回已保存值
function undoOne(key) {
  const item = settingsItems.value.find((it) => it.key === key)
  if (item) form[key] = item.current
}

// 放弃全部改动：退回已保存值（与「恢复出厂默认值」不同，后者退回注册表默认值）
function discardAll() {
  for (const item of settingsItems.value) {
    form[item.key] = item.current
  }
}

// 保存条收起时同步收起展开态，避免下次展开残留
watch(barVisible, (on) => {
  if (!on) barOpen.value = false
})

async function onSaveSettings() {
  // 仅提交发生变化的键，减少误覆盖
  const changed = {}
  for (const item of settingsItems.value) {
    if (form[item.key] !== undefined && form[item.key] !== item.current) {
      changed[item.key] = form[item.key]
    }
  }
  if (!Object.keys(changed).length) return

  saving.value = true
  try {
    const data = await updateSettings(changed)
    applyItems(data.items)
    toast('设置已保存', 'success')
    savedFlash.value = true
    clearTimeout(savedFlashTimer)
    savedFlashTimer = setTimeout(() => {
      savedFlash.value = false
    }, 1800)
  } catch {
    /* 失败已由 request.js 全局 toast 提示 */
  } finally {
    saving.value = false
  }
}

watch(savedFlash, async (on) => {
  if (!on || REDUCED_MOTION) return
  await nextTick()
  if (!receiptRef.value) return
  gsap.fromTo(
    receiptRef.value,
    { scale: 0.96, opacity: 0.4 },
    { scale: 1, opacity: 1, duration: 0.35, ease: 'back.out(2)', clearProps: 'transform,opacity' }
  )
})

// ==================== 区四：系统运行（仅管理员） ====================
const sysInfo = ref(null)
const infoLoading = ref(false)
const versionRef = ref(null)

const dbOk = computed(() => sysInfo.value?.database?.status === 'ok')
// 环境状态点：生产绿（稳定信号）/ 非生产琥珀（提示信号）；徽标文字恒白，颜色只落在圆点上
const envDotCls = computed(() => (sysInfo.value?.env === 'production' ? 'bg-success' : 'bg-amber'))
const envLabel = computed(() => {
  if (!sysInfo.value) return '-'
  return sysInfo.value.debug ? '开发环境' : sysInfo.value.env === 'production' ? '生产环境' : sysInfo.value.env
})
const uptimeLabel = computed(() => formatUptime(sysInfo.value?.uptime_seconds))
const startedAtLabel = computed(() => {
  const raw = sysInfo.value?.started_at
  // 启动时间太长，截取 MM-DD HH:mm 放入副文本位
  return raw ? '启动于 ' + raw.slice(5, 16) : ''
})
const usersTotal = computed(() => String(sysInfo.value?.users?.total ?? '-'))

function formatUptime(seconds) {
  if (seconds === undefined || seconds === null) return '-'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return d + ' 天 ' + h + ' 小时'
  if (h > 0) return h + ' 小时 ' + m + ' 分'
  return m + ' 分钟'
}

async function loadSystemInfo() {
  infoLoading.value = true
  try {
    sysInfo.value = await getSystemInfo()
  } catch {
    /* 失败已由 request.js 全局 toast 提示 */
  } finally {
    infoLoading.value = false
  }
}

// 版本号刷新（首次加载或手动刷新）时轻淡入，提示"这是最新读数"
watch(
  () => sysInfo.value?.version,
  async () => {
    if (REDUCED_MOTION || !versionRef.value) return
    await nextTick()
    gsap.fromTo(
      versionRef.value,
      { opacity: 0, y: 4 },
      { opacity: 1, y: 0, duration: 0.4, ease: 'power2.out', clearProps: 'opacity,transform' }
    )
  }
)

onMounted(async () => {
  // 账户信息/账户安全对所有角色可用；系统参数/系统运行仅管理员加载（后端同样做了 admin 校验）
  loadAccountInfo()
  if (auth.isAdmin) {
    loadSettings()
    loadSystemInfo()
  }
  await nextTick()
  setupSpy()
  measureMarker()
  // 视口变化会让目录项换行、字体加载完成也会让文字重新排版——两者都会挪动定位标的落点
  window.addEventListener('resize', measureMarker)
  document.fonts?.ready.then(measureMarker)
})

onBeforeUnmount(() => {
  clearTimeout(savedFlashTimer)
  spy?.disconnect()
  window.removeEventListener('resize', measureMarker)
})
</script>

<style scoped>
/* 移动端目录 chip 轨：隐藏滚动条但保留滚动能力（触控横滑） */
.chip-scroll::-webkit-scrollbar {
  display: none;
}

/* 浮动保存条：有改动时上浮入场、清空后下沉收场 */
.savebar-enter-active,
.savebar-leave-active {
  transition: opacity 0.22s ease, transform 0.22s cubic-bezier(0.22, 0.61, 0.36, 1);
}
.savebar-enter-from,
.savebar-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

@media (prefers-reduced-motion: reduce) {
  .savebar-enter-active,
  .savebar-leave-active {
    transition: none;
  }
  .savebar-enter-from,
  .savebar-leave-to {
    transform: none;
  }
}
</style>
