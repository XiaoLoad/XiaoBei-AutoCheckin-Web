<template>
  <div class="fixed inset-0 z-50">
    <!-- 遮罩 -->
    <div ref="overlay" class="absolute inset-0 bg-ink/40" @click="requestClose" />

    <!-- 右滑抽屉面板 -->
    <aside
      ref="panel"
      class="absolute right-0 top-0 flex h-full w-full max-w-xl flex-col bg-white shadow-2xl"
      role="dialog"
      aria-modal="true"
    >
      <header class="flex shrink-0 items-center justify-between gap-3 border-b border-ink/10 px-6 py-5">
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span class="grid h-8 w-8 place-items-center rounded-xl bg-brand/10 text-brand">
              <Icon name="sliders" :size="16" />
            </span>
            <h3 class="text-lg font-semibold text-ink">批量管理任务</h3>
          </div>
          <p class="mt-2 truncate pl-10 text-xs text-ink-muted">批量开启或关闭多个账号的定时签到</p>
        </div>
        <button type="button" class="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud" aria-label="关闭" @click="requestClose">
          <Icon name="close" :size="20" />
        </button>
      </header>

      <!-- ═══ 结果视图：动作感知横幅 + 双统计卡 + 操作指引 + 分组明细 ═══ -->
      <template v-if="result">
        <div class="xb-scroll min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <!-- 结论横幅：图标 + 一句话结论 -->
          <div class="flex items-center gap-3 rounded-2xl px-5 py-4" :class="outcomeBandClass">
            <span class="grid h-12 w-12 shrink-0 place-items-center rounded-full" :class="outcomeIconWrap">
              <Icon :name="outcomeIcon" :size="26" />
            </span>
            <div class="min-w-0">
              <p class="text-base font-semibold leading-tight">{{ outcomeTitle }}</p>
              <p class="mt-0.5 text-xs opacity-80">{{ outcomeSub }}</p>
            </div>
          </div>

          <!-- 双统计卡：已启用/关闭 + 未处理 -->
          <div class="mt-4 grid grid-cols-2 gap-3">
            <div class="rounded-2xl border px-5 py-4" :class="statPrimaryClass">
              <div class="flex items-center gap-1.5 text-xs font-medium">
                <Icon :name="result.action === 'disable' ? 'x-circle' : 'check-circle'" :size="14" />
                {{ result.action === 'disable' ? '已关闭' : '已启用' }}
              </div>
              <p class="mt-1.5 text-3xl font-semibold leading-none text-ink">{{ result.affected }}</p>
              <p class="mt-1.5 text-[11px] opacity-70">个账号任务</p>
            </div>
            <div v-if="result.skipped" class="rounded-2xl border border-amber/30 bg-amber/5 px-5 py-4">
              <div class="flex items-center gap-1.5 text-xs font-medium text-amber">
                <Icon name="alert" :size="14" /> 未处理
              </div>
              <p class="mt-1.5 text-3xl font-semibold leading-none text-ink">{{ result.skipped }}</p>
              <p class="mt-1.5 text-[11px] text-ink-muted">个账号任务</p>
            </div>
          </div>

          <!-- 操作指引 -->
          <p class="mt-4 rounded-xl bg-cloud/60 px-4 py-3 text-xs leading-relaxed text-ink-soft">
            {{ guidance }}
          </p>

          <!-- 成功/已处理明细：按账号分组 -->
          <section v-if="groupedAffected.length" class="mt-5">
            <h4 class="mb-2.5 flex items-center gap-1.5 text-sm font-medium text-ink-soft">
              <Icon :name="result.action === 'disable' ? 'x-circle' : 'check-circle'" :size="15" :class="result.action === 'disable' ? 'text-warning' : 'text-success'" />
              {{ result.action === 'disable' ? '已关闭' : '已启用' }}（{{ result.affected }}）
            </h4>
            <div class="space-y-2.5">
              <div
                v-for="g in groupedAffected"
                :key="g.accountId"
                class="xb-result-row flex items-center gap-3 rounded-xl border px-4 py-3"
                :class="result.action === 'disable' ? 'border-warning/20 bg-warning/5' : 'border-success/20 bg-success/5'"
              >
                <span class="grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-semibold"
                  :class="result.action === 'disable' ? 'bg-warning/15 text-warning' : 'bg-success/15 text-success'">
                  {{ g.accountName.charAt(0) }}
                </span>
                <div class="min-w-0 flex-1">
                  <p class="truncate text-sm font-medium text-ink">{{ g.accountName }}</p>
                  <div class="mt-1.5 flex flex-wrap gap-1">
                    <span
                      v-for="t in g.tasks"
                      :key="t"
                      class="rounded-full border px-2.5 py-0.5 text-[11px] leading-4"
                      :class="result.action === 'disable' ? 'border-warning/25 bg-white text-warning' : 'border-success/25 bg-white text-success'"
                    >{{ t }}</span>
                  </div>
                </div>
                <Icon name="check" :size="16" class="shrink-0" :class="result.action === 'disable' ? 'text-warning' : 'text-success'" />
              </div>
            </div>
          </section>

          <!-- 跳过明细 -->
          <section v-if="result.skippedReasons.length" class="mt-5">
            <h4 class="mb-2.5 flex items-center gap-1.5 text-sm font-medium text-ink-soft">
              <Icon name="alert" :size="15" class="text-amber" />
              未处理（{{ result.skippedReasons.length }}）
            </h4>
            <div class="space-y-2.5">
              <div
                v-for="(s, i) in result.skippedReasons"
                :key="i"
                class="xb-result-row rounded-xl border border-amber/30 bg-amber/5 px-4 py-3"
              >
                <p class="text-sm font-medium text-ink">{{ s.accountName }} · {{ s.taskLabel }}</p>
                <p class="mt-1 text-xs leading-relaxed text-ink-muted">{{ s.reason }}</p>
              </div>
            </div>
          </section>

          <p v-if="!result.affected && !result.skippedReasons.length" class="mt-5 text-center text-xs text-ink-muted">
            没有需要处理的目标任务。
          </p>
        </div>

        <footer class="shrink-0 border-t border-ink/10 px-6 py-4">
          <div class="flex items-center justify-between gap-3">
            <button
              type="button"
              class="inline-flex h-10 items-center gap-1.5 rounded-lg border border-ink/10 px-4 text-sm font-medium text-ink-soft transition hover:bg-cloud"
              @click="backToSelect"
            >
              <Icon name="chevron-left" :size="15" />返回继续管理
            </button>
            <button
              type="button"
              class="inline-flex h-10 items-center rounded-lg bg-brand px-6 text-sm font-medium text-white transition hover:bg-brand-dark"
              @click="requestClose"
            >
              完成
            </button>
          </div>
        </footer>
      </template>

      <!-- ═══ 选择视图 ═══ -->
      <template v-else>
        <!-- 模式切换：批量启用 / 批量关闭 -->
        <div class="shrink-0 px-6 pt-5">
          <div class="grid grid-cols-2 gap-1.5 rounded-2xl bg-cloud/70 p-1.5">
            <button
              type="button"
              class="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl text-sm font-medium transition"
              :class="mode === 'enable' ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink'"
              @click="setMode('enable')"
            >
              <Icon name="check-circle" :size="16" />批量启用
            </button>
            <button
              type="button"
              class="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl text-sm font-medium transition"
              :class="mode === 'disable' ? 'bg-white text-warning shadow-sm' : 'text-ink-muted hover:text-ink'"
              @click="setMode('disable')"
            >
              <Icon name="x-circle" :size="16" />批量关闭
            </button>
          </div>
        </div>

        <!-- 模式说明 -->
        <div
          class="mx-6 mt-4 shrink-0 rounded-xl border-l-4 px-4 py-3 text-xs leading-relaxed text-ink-soft"
          :class="mode === 'enable' ? 'border-brand/40 bg-brand/5' : 'border-amber/40 bg-amber/5'"
        >
          {{ hintText }}
        </div>

        <!-- 可选配置套（仅启用模式需要） -->
        <div v-if="mode === 'enable'" class="shrink-0 px-6 pt-4">
          <label class="mb-1.5 block text-[11px] text-ink-muted">配置套（可选）</label>
          <div class="w-full">
            <BaseSelect v-model="pickSetId" :options="setPickOptions" :searchable="true" size="sm" placeholder="不设置（用各自现有配置）" />
          </div>
        </div>

        <!-- 模糊搜索：账号名称 / 学号 / 班级，空格分词 AND 匹配 -->
        <div class="shrink-0 px-6 pt-4">
          <div class="relative">
            <Icon name="search" :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
            <input
              v-model="query"
              type="text"
              placeholder="搜索账号名称 / 学号 / 班级，空格分隔多关键词"
              class="h-10 w-full rounded-lg border border-ink/10 bg-cloud/40 pl-9 pr-8 text-sm text-ink outline-none transition placeholder:text-ink-muted/70 focus:border-brand/40 focus:bg-white focus:ring-2 focus:ring-brand/10"
            />
            <button
              v-if="query"
              type="button"
              class="absolute right-2 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-md text-ink-muted transition hover:bg-ink/5"
              aria-label="清除搜索"
              @click="query = ''"
            >
              <Icon name="close" :size="14" />
            </button>
          </div>
        </div>

        <!-- 批量工具条：全选 / 反选 / 按类型刷选 /（关闭模式）只看运行中 -->
        <div v-if="accounts.length" class="shrink-0 px-6 pt-3">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-[11px] text-ink-muted">批量：</span>
            <button
              type="button"
              class="inline-flex h-8 items-center rounded-lg border px-3 text-xs font-medium transition"
              :class="allSelected
                ? 'border-brand bg-brand text-white'
                : 'border-ink/10 bg-white text-ink-soft hover:border-brand/30 hover:bg-brand/5 hover:text-brand'"
              :disabled="applyablePairs.length === 0"
              @click="selectAllTasks"
            >
              {{ allSelected ? '清空' : '全选' }}
            </button>
            <button
              type="button"
              class="inline-flex h-8 items-center rounded-lg border border-ink/10 bg-white px-3 text-xs font-medium text-ink-soft transition hover:border-brand/30 hover:bg-brand/5 hover:text-brand disabled:opacity-50"
              :disabled="applyablePairs.length === 0"
              @click="invertSelection"
            >
              反选
            </button>
            <span class="mx-0.5 h-4 w-px bg-ink/10" aria-hidden="true"></span>
            <span class="text-[11px] text-ink-muted">按类型：</span>
            <button
              v-for="t in taskTypes"
              :key="t.value"
              type="button"
              class="inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-xs font-medium transition"
              :class="typeCounts[t.value]
                ? 'border-brand/30 bg-brand/10 text-brand'
                : 'border-ink/10 bg-white text-ink-soft hover:border-brand/30 hover:bg-brand/5 hover:text-brand'"
              :title="brushTitle(t)"
              @click="selectByType(t.value)"
            >
              只选{{ t.label }}
              <span
                v-if="typeCounts[t.value]"
                class="rounded-full bg-brand px-1.5 text-[10px] leading-4 text-white"
              >{{ typeCounts[t.value] }}</span>
            </button>
            <button
              v-if="mode === 'disable'"
              type="button"
              class="inline-flex h-8 items-center gap-1 rounded-lg border px-3 text-xs font-medium transition"
              :class="onlyRunning
                ? 'border-warning/40 bg-warning/10 text-warning'
                : 'border-ink/10 bg-white text-ink-soft hover:border-brand/30 hover:bg-brand/5 hover:text-brand'"
              @click="onlyRunning = !onlyRunning"
            >
              {{ onlyRunning ? '显示全部账号' : '只看运行中' }}
            </button>
          </div>
          <p class="mt-2 text-[11px] leading-relaxed text-ink-muted">{{ brushHint }}</p>
        </div>

        <!-- 账号列表：干净的花名册（细线分隔 + 紧凑行 + 左侧选择轨） -->
        <div class="xb-scroll min-h-0 flex-1 overflow-y-auto">
          <div v-if="accounts.length === 0" class="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
            <span class="grid h-14 w-14 place-items-center rounded-full bg-brand/10 text-brand">
              <Icon name="users" :size="24" />
            </span>
            <p class="text-sm font-medium text-ink">暂无平台账号</p>
            <p class="text-xs leading-relaxed text-ink-muted">先到「账号管理」添加账号，再回来批量管理。</p>
          </div>

          <div v-else-if="filtered.length === 0" class="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
            <p class="text-sm font-medium text-ink">没有符合条件的账号</p>
            <p class="text-xs text-ink-muted">{{ emptyHint }}</p>
          </div>

          <template v-else>
            <ul class="divide-y divide-ink/10">
              <li
                v-for="acc in visible"
                :key="acc.id"
                class="xb-apply-acc relative flex items-center gap-3 px-6 py-3 transition hover:bg-cloud/40"
                :class="accHasSelection(acc) ? 'bg-brand/[0.04]' : ''"
              >
                <!-- 选择左轨：该行有任一项被选中时显示，作为可扫读的状态锚 -->
                <span
                  v-if="accHasSelection(acc)"
                  class="absolute left-0 top-1/2 h-7 w-1 -translate-y-1/2 rounded-r bg-brand"
                  aria-hidden="true"
                />
                <!-- 账号级勾选 -->
                <button
                  type="button"
                  class="grid h-5 w-5 shrink-0 place-items-center rounded-md border transition"
                  :class="accChecked(acc.id)
                    ? 'border-brand bg-brand text-white'
                    : accountSelectable(acc)
                      ? 'border-ink/25 bg-white text-transparent hover:border-brand/50'
                      : 'border-ink/15 bg-cloud/60 text-transparent cursor-not-allowed'"
                  :disabled="!accountSelectable(acc)"
                  :title="accountSelectable(acc) ? (accChecked(acc.id) ? '取消勾选该账号全部任务' : '勾选该账号全部任务') : accountDisabledTitle(acc)"
                  :aria-label="`勾选 ${acc.name} 的全部任务`"
                  @click="toggleAccount(acc)"
                >
                  <Icon name="check" :size="13" />
                </button>
                <!-- 头像 -->
                <div class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand/10 text-sm font-semibold text-brand">
                  {{ acc.name.charAt(0) }}
                </div>
                <!-- 身份 -->
                <div class="min-w-0 flex-1">
                  <p class="truncate text-sm font-medium text-ink">
                    {{ acc.name }}
                    <span v-if="!accEnabled(acc)" class="ml-1.5 rounded-full bg-ink/5 px-1.5 py-0.5 text-[10px] font-normal text-ink-muted">账号未启用</span>
                  </p>
                  <p class="truncate text-[11px] text-ink-muted">
                    <template v-if="acc.studentNo">{{ acc.studentNo }}</template>
                    <template v-if="acc.studentNo && acc.className"> · </template>
                    <template v-if="acc.className">{{ acc.className }}</template>
                  </p>
                </div>
                <!-- 任务类型切换（紧凑 pill，含运行中点） -->
                <div class="flex shrink-0 items-center gap-1.5">
                  <button
                    v-for="t in taskTypes"
                    :key="t.value"
                    type="button"
                    class="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition"
                    :class="isChecked(acc.id, t.value)
                      ? 'border-brand bg-brand text-white'
                      : taskSelectable(acc, t.value)
                        ? 'border-ink/10 bg-white text-ink-soft hover:border-brand/30'
                        : 'cursor-not-allowed border-ink/10 bg-white text-ink-muted opacity-55'"
                    :disabled="!taskSelectable(acc, t.value)"
                    :title="taskSelectable(acc, t.value) ? '' : taskDisabledTitle(acc, t.value)"
                    @click="toggleTask(acc.id, t.value)"
                  >
                    <span
                      class="h-1.5 w-1.5 rounded-full"
                      :class="isChecked(acc.id, t.value) ? 'bg-white' : (taskRunning(acc.id, t.value) ? 'bg-success' : 'bg-ink/25')"
                    />
                    <span>{{ t.label }}</span>
                    <span v-if="taskRunning(acc.id, t.value)" class="text-[10px] opacity-70">运行中</span>
                  </button>
                </div>
              </li>
            </ul>

            <!-- 列表较长时的单一安静入口，不带任何分组家具 -->
            <button
              v-if="filtered.length > visible.length"
              type="button"
              class="w-full py-3 text-center text-xs font-medium text-brand transition hover:bg-brand/5"
              @click="cap = filtered.length"
            >
              显示全部 {{ filtered.length }} 个账号
            </button>
          </template>
        </div>

        <!-- 底部操作条：统计 + 执行（行内二次确认 / 已启用覆盖确认） -->
        <footer class="shrink-0 border-t border-ink/10 px-6 py-4">
          <!-- 选择态 -->
          <template v-if="confirming === false">
            <div class="flex items-center justify-between gap-3">
              <p class="min-w-0 truncate text-xs text-ink-muted">
                <template v-if="selectedCount">
                  已选 <span class="font-semibold text-ink">{{ selectedCount }}</span> 个任务 · {{ selectedAccountsCount }} 个账号
                </template>
                <template v-else>勾选账号或任务后{{ verb }}，可用上方「批量」工具快速选择</template>
              </p>
              <div class="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  class="inline-flex h-10 items-center gap-1.5 rounded-lg px-4 text-sm font-medium text-white transition disabled:opacity-50"
                  :class="mode === 'enable' ? 'bg-brand hover:bg-brand-dark' : 'bg-warning hover:bg-warning/90'"
                  :disabled="selectedCount === 0 || store.saving"
                  @click="onPrimaryClick"
                >
                  <Icon :name="mode === 'enable' ? 'check-circle' : 'x-circle'" :size="15" />
                  {{ store.saving ? verb + '中…' : verb + '所选' }}
                </button>
              </div>
            </div>
          </template>

          <!-- 普通确认态 -->
          <template v-else-if="confirming === true">
            <div class="flex items-center justify-between gap-3">
              <p class="min-w-0 text-xs leading-relaxed text-ink-soft">{{ confirmText }}</p>
              <div class="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  class="inline-flex h-10 items-center rounded-lg border border-ink/10 px-4 text-sm font-medium text-ink-soft transition hover:bg-cloud"
                  @click="confirming = false"
                >
                  取消
                </button>
                <button
                  type="button"
                  class="inline-flex h-10 items-center rounded-lg px-4 text-sm font-medium text-white transition disabled:opacity-50"
                  :class="mode === 'enable' ? 'bg-brand hover:bg-brand-dark' : 'bg-warning hover:bg-warning/90'"
                  :disabled="store.saving"
                  @click="onApply"
                >
                  {{ store.saving ? verb + '中…' : '确认' + verb }}
                </button>
              </div>
            </div>
          </template>

          <!-- 已启用覆盖确认态 -->
          <template v-else>
            <div class="space-y-3">
              <div class="rounded-xl border border-amber/30 bg-amber/5 px-4 py-3">
                <p class="flex items-center gap-1.5 text-xs font-medium text-amber">
                  <Icon name="alert" :size="14" /> 已选任务中有 {{ alreadyEnabled.length }} 个已处于启用状态
                </p>
                <p class="mt-1 text-[11px] leading-relaxed text-ink-soft">
                  继续将按当前设置覆盖这些任务的调度（重新计算下次运行时间{{ pickSetId ? '，并套用所选配置套' : '' }}）；未启用的任务仍会正常启用。
                </p>
                <div class="mt-2 flex flex-wrap gap-1">
                  <span
                    v-for="e in alreadyEnabled"
                    :key="e.accId + ':' + e.type"
                    class="rounded-full border border-amber/25 bg-white px-2 py-0.5 text-[10px] leading-4 text-amber"
                  >{{ e.name }} · {{ e.taskLabel }}</span>
                </div>
              </div>
              <div class="flex items-center justify-end gap-2">
                <button
                  type="button"
                  class="inline-flex h-10 items-center rounded-lg border border-ink/10 px-4 text-sm font-medium text-ink-soft transition hover:bg-cloud"
                  @click="confirming = false"
                >
                  返回
                </button>
                <button
                  type="button"
                  class="inline-flex h-10 items-center gap-1.5 rounded-lg bg-brand px-4 text-sm font-medium text-white transition disabled:opacity-50"
                  :disabled="store.saving"
                  @click="onApply"
                >
                  <Icon name="check-circle" :size="15" />
                  {{ store.saving ? '启用中…' : '继续覆盖' }}
                </button>
              </div>
            </div>
          </template>
        </footer>
      </template>
    </aside>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { useSchedulesStore } from '@/stores/schedules'

const emit = defineEmits(['close'])

const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const overlay = ref(null)
const panel = ref(null)
const closing = ref(false)

const store = useSignConfigStore()
const schedulesStore = useSchedulesStore()

const accounts = computed(() => store.accounts)
const taskTypes = computed(() => store.taskTypes)

// ── 模式：enable 批量启用 / disable 批量关闭 ──
const mode = ref('enable')
const verb = computed(() => (mode.value === 'disable' ? '关闭' : '启用'))

const hintText = computed(() =>
  mode.value === 'enable'
    ? '可选「配置套」：不选则各任务用自身现有配置启用；选择则先覆盖套用该配置套再启用。未启用账号或缺少配置的任务会被跳过并列出原因。'
    : '关闭后任务不再自动签到，配置保留、可随时重新启用。当前未在启用中的任务会被跳过并列出原因。'
)

const confirmText = computed(() =>
  mode.value === 'enable'
    ? `将启用所选 ${selectedCount.value} 个任务${pickSetId.value ? '，并统一套用所选配置套' : ''}。`
    : `将关闭所选 ${selectedCount.value} 个任务，关闭后不再自动签到（配置保留）。`
)

// 可选配置套：前置一个「不设置」空选项（值 ''），默认不套用、用各自现有配置
const pickSetId = ref('')
const setPickOptions = computed(() => [
  { label: '不设置（用各自现有配置）', value: '' },
  ...store.setOptions,
])

const accEnabled = (acc) => acc.status === 'enabled'
// 某「账号 × 任务」当前是否处于启用中（来自后端任务实例绑定）
const taskRunning = (accId, taskType) => {
  const b = store.scheduleBindings && store.scheduleBindings[`${accId}:${taskType}`]
  return !!(b && b.enabled)
}
const runningCountOf = (acc) => taskTypes.value.filter((t) => taskRunning(acc.id, t.value)).length

// ── 可选性：启用模式要求账号启用；关闭模式要求该任务当前处于启用中 ──
const taskSelectable = (acc, taskType) =>
  mode.value === 'enable' ? accEnabled(acc) : taskRunning(acc.id, taskType)
const accountSelectable = (acc) =>
  mode.value === 'enable' ? accEnabled(acc) : runningCountOf(acc) > 0

const taskDisabledTitle = (acc, taskType) =>
  mode.value === 'enable' ? '账号未启用，无法启用' : '该任务未在启用中，无需关闭'
const accountDisabledTitle = (acc) =>
  mode.value === 'enable' ? '账号未启用，无法启用' : '该账号没有正在运行的任务'

// 当前模式下可参与批量操作的「账号 × 任务」全集（全选/反选/类型刷选的作用域）
const applyablePairs = computed(() => {
  const pairs = []
  for (const acc of accounts.value) {
    for (const t of taskTypes.value) {
      if (taskSelectable(acc, t.value)) pairs.push({ accId: acc.id, type: t.value })
    }
  }
  return pairs
})

// ── 选择状态：Set<`${accountId}:${taskType}`>，替换实例保证响应式 ──
const selected = ref(new Set())
const keyOf = (accId, type) => `${accId}:${type}`
const isChecked = (accId, type) => selected.value.has(keyOf(accId, type))
// 账号级复选框：该账号名下「当前可选的」任务全部被勾选才算选中
const accChecked = (accId) => {
  const acc = accounts.value.find((a) => String(a.id) === String(accId))
  if (!acc) return false
  const selectable = taskTypes.value.filter((t) => taskSelectable(acc, t.value))
  if (!selectable.length) return false
  return selectable.every((t) => isChecked(accId, t.value))
}
// 该行是否已有任一项被选中（驱动左侧选择轨与整行底色）
const accHasSelection = (acc) => taskTypes.value.some((t) => isChecked(acc.id, t.value))

function toggleTask(accId, type) {
  const next = new Set(selected.value)
  const k = keyOf(accId, type)
  if (next.has(k)) next.delete(k)
  else next.add(k)
  selected.value = next
}

function toggleAccount(acc) {
  if (!accountSelectable(acc)) return
  const next = new Set(selected.value)
  const allOn = accChecked(acc.id)
  for (const t of taskTypes.value) {
    if (!taskSelectable(acc, t.value)) continue
    const k = keyOf(acc.id, t.value)
    if (allOn) next.delete(k)
    else next.add(k)
  }
  selected.value = next
}

// 全选：已全选时再次点击 -> 清空（便捷的批量不选 / 反选入口）
const allSelected = computed(() => {
  const pairs = applyablePairs.value
  if (!pairs.length) return false
  return pairs.every((p) => selected.value.has(keyOf(p.accId, p.type)))
})
function selectAllTasks() {
  if (allSelected.value) {
    selected.value = new Set()
    return
  }
  const next = new Set()
  for (const p of applyablePairs.value) next.add(keyOf(p.accId, p.type))
  selected.value = next
}

// 反选：在可选全集内对每个键取反（不可选项始终保持未选）
function invertSelection() {
  const next = new Set()
  for (const p of applyablePairs.value) {
    const k = keyOf(p.accId, p.type)
    if (!selected.value.has(k)) next.add(k)
  }
  selected.value = next
}

const selectedCount = computed(() => selected.value.size)
const selectedAccountsCount = computed(() => {
  const ids = new Set()
  for (const k of selected.value) ids.add(String(k).split(':')[0])
  return ids.size
})
// 已选账号（仅当前模式下仍可选的）：类型刷选的作用域
const selectedAccounts = computed(() => {
  const ids = new Set()
  for (const k of selected.value) ids.add(String(k).split(':')[0])
  return accounts.value.filter((a) => ids.has(String(a.id)) && accountSelectable(a))
})

// 按类型刷选：把作用域内账号的勾选收敛为「仅该类型」（不可选的组合不会凭空加入）
function selectByType(type) {
  const scopeIds = new Set(selectedAccounts.value.map((a) => String(a.id)))
  const inScope = (accId) => scopeIds.size === 0 || scopeIds.has(String(accId))
  const next = new Set(selected.value)
  for (const p of applyablePairs.value) {
    if (inScope(p.accId)) next.delete(keyOf(p.accId, p.type))
  }
  for (const p of applyablePairs.value) {
    if (inScope(p.accId) && p.type === type) next.add(keyOf(p.accId, p.type))
  }
  selected.value = next
}

const typeCounts = computed(() => {
  const counts = {}
  for (const t of taskTypes.value) {
    let n = 0
    for (const k of selected.value) if (k.endsWith(`:${t.value}`)) n++
    counts[t.value] = n
  }
  return counts
})

// 类型刷选的作用域说明（按钮 title 与工具条下方提示共用口径）
const scopeText = computed(() => {
  const n = selectedAccounts.value.length
  if (n) return `已选的 ${n} 个账号`
  return mode.value === 'enable'
    ? `全部 ${accounts.value.filter(accEnabled).length} 个已启用账号`
    : `全部 ${accounts.value.filter((a) => runningCountOf(a) > 0).length} 个有运行中任务的账号`
})
const brushTitle = (t) => `把${scopeText.value}的勾选收敛为仅「${t.label}」`
const brushHint = computed(() =>
  accounts.value.length
    ? `类型刷选作用于${scopeText.value}：点击后这些账号仅保留该类型勾选；先「全选」再点类型即可只跑一种签到。`
    : ''
)

// ── 模糊搜索 +（关闭模式）只看运行中筛选 ──
const query = ref('')
const onlyRunning = ref(true)
const norm = (v) => String(v || '').toLowerCase()
const emptyHint = computed(() => {
  if (query.value) return '换个关键词试试，或清空搜索查看全部账号。'
  return mode.value === 'disable' && onlyRunning.value
    ? '当前没有正在运行的任务，可点「显示全部账号」查看。'
    : '换个筛选条件试试。'
})
const filtered = computed(() => {
  let list = accounts.value
  if (mode.value === 'disable' && onlyRunning.value) {
    list = list.filter((a) => runningCountOf(a) > 0)
  }
  const tokens = norm(query.value).split(/\s+/).filter(Boolean)
  if (tokens.length) {
    list = list.filter((a) => {
      const hay = norm(`${a.name} ${a.studentNo} ${a.className} ${a.platform}`)
      return tokens.every((t) => hay.includes(t))
    })
  }
  return list
})

// 列表首屏上限：紧凑行每屏约 8-9 条；超出时底部提供单一「显示全部」入口
const cap = ref(20)
const visible = computed(() => filtered.value.slice(0, cap.value))
watch(query, () => { cap.value = 20 })

// 切换模式：语义不同，清空选择与配置套，避免误操作沿用上一模式的选择
function setMode(next) {
  if (mode.value === next) return
  mode.value = next
  selected.value = new Set()
  pickSetId.value = ''
  query.value = ''
  cap.value = 20
  confirming.value = false
  if (next === 'disable') onlyRunning.value = true
}

// ── 执行结果：{action, affected, skipped, skippedReasons, affectedList} ──
const result = ref(null)
const appliedSetName = ref('') // 结果页上下文：本次启用所套用的配置套名称
// 确认态：false 选择态 / true 普通确认 / 'overwrite' 已启用覆盖确认
const confirming = ref(false)

// 启用模式下，已选任务中处于启用状态的（覆盖前需用户二次确认）
const alreadyEnabled = computed(() => {
  if (mode.value !== 'enable') return []
  const out = []
  for (const k of selected.value) {
    const [accId, type] = k.split(':')
    if (taskRunning(accId, type)) {
      const acc = accounts.value.find((a) => String(a.id) === String(accId))
      const tl = taskTypes.value.find((t) => t.value === type)
      out.push({ accId, type, name: acc ? acc.name : `账号${accId}`, taskLabel: tl ? tl.label : type })
    }
  }
  return out
})

// 主操作按钮：启用模式且有已启用任务时，先走覆盖确认；否则普通确认
function onPrimaryClick() {
  if (selectedCount.value === 0) return
  if (mode.value === 'enable' && alreadyEnabled.value.length) {
    confirming.value = 'overwrite'
  } else {
    confirming.value = true
  }
}

async function onApply() {
  const targets = [...selected.value].map((k) => {
    const [accountId, taskType] = k.split(':')
    return { accountId: Number(accountId), taskType }
  })
  // 记录本次启用的配置套名称，供结果页上下文提示
  appliedSetName.value = ''
  if (mode.value === 'enable' && pickSetId.value) {
    const opt = setPickOptions.value.find((o) => String(o.value) === String(pickSetId.value))
    appliedSetName.value = opt ? opt.label : ''
  }
  const data = await store.batchManageTasks(targets, {
    action: mode.value,
    configSetId: mode.value === 'enable' ? (pickSetId.value || null) : null,
  })
  confirming.value = false
  if (!data) return
  result.value = {
    action: data.action || mode.value,
    affected: data.affected || 0,
    skipped: data.skipped || 0,
    skippedReasons: data.skippedReasons || [],
    affectedList: data.affectedList || [],
  }
  // 同步刷新定时任务页（若用户停留在其它 tab，无感知失败）
  try {
    await schedulesStore.load()
  } catch (e) {
    /* 非当前视图，忽略 */
  }
  await nextTick()
  revealResultRows()
}

// 结果页：成功明细按账号分组，一行一账号、名下任务以 chip 列出
const groupedAffected = computed(() => {
  if (!result.value) return []
  const byAcc = new Map()
  for (const it of result.value.affectedList) {
    const k = String(it.accountId)
    if (!byAcc.has(k)) {
      byAcc.set(k, { accountId: k, accountName: it.accountName || '未命名账号', tasks: [] })
    }
    byAcc.get(k).tasks.push(it.taskLabel)
  }
  return [...byAcc.values()]
})

// ── 结果页：动作感知的友好呈现 ──
const outcomeIcon = computed(() => {
  const r = result.value
  if (!r || !r.affected) return 'alert'
  return r.skipped ? 'alert' : (r.action === 'disable' ? 'x-circle' : 'check-circle')
})
const outcomeTitle = computed(() => {
  const r = result.value
  if (!r) return ''
  const v = r.action === 'disable' ? '关闭' : '启用'
  if (!r.affected && !r.skipped) return `没有可${v}的目标任务`
  if (r.affected && !r.skipped) return `已成功${v} ${r.affected} 个任务`
  if (r.affected && r.skipped) return `${v}成功 ${r.affected} 个，跳过 ${r.skipped} 个`
  return `所选任务均无需${v}`
})
const outcomeSub = computed(() => {
  const r = result.value
  if (!r) return ''
  if (r.affected && !r.skipped) return `涉及 ${groupedAffected.value.length} 个账号`
  if (r.affected && r.skipped) return '部分任务因缺少配置或未启用被跳过'
  return '跳过原因见下方明细'
})
const outcomeBandClass = computed(() => {
  const r = result.value
  if (!r || !r.affected) return 'border-amber/30 bg-amber/5 text-ink'
  return r.skipped ? 'border-amber/30 bg-amber/5 text-ink' : 'border-success/25 bg-success/5 text-ink'
})
const outcomeIconWrap = computed(() => {
  const r = result.value
  if (!r || !r.affected) return 'bg-amber/15 text-amber'
  return r.skipped ? 'bg-amber/15 text-amber' : 'bg-success/15 text-success'
})
const statPrimaryClass = computed(() => {
  const r = result.value
  if (!r) return 'border-success/25 bg-success/5'
  return r.action === 'disable' ? 'border-warning/30 bg-warning/5' : 'border-success/25 bg-success/5'
})
const guidance = computed(() => {
  const r = result.value
  if (!r) return ''
  const parts = []
  if (r.action === 'disable') {
    parts.push('已关闭的任务停止自动签到，原有配置已保留；需要时可随时回到这里重新启用。')
  } else {
    parts.push('启用后任务将在各自设定的签到时间自动打卡，可在「定时任务」页查看下次运行时间。')
    if (appliedSetName.value) parts.push(`本次已统一套用配置套「${appliedSetName.value}」。`)
  }
  if (r.skipped) parts.push('部分任务未处理，原因见下方明细。')
  return parts.join('')
})

function backToSelect() {
  result.value = null
  selected.value = new Set()
  confirming.value = false
  nextTick(revealRows)
}

function revealRows() {
  if (prefersReduced || !panel.value) return
  const rows = panel.value.querySelectorAll('.xb-apply-acc')
  if (rows.length) {
    gsap.fromTo(
      rows,
      { opacity: 0, y: 12 },
      { opacity: 1, y: 0, duration: 0.4, stagger: 0.04, ease: 'power2.out', clearProps: 'opacity,transform' }
    )
  }
}

function revealResultRows() {
  if (prefersReduced || !panel.value) return
  const rows = panel.value.querySelectorAll('.xb-result-row')
  if (rows.length) {
    gsap.fromTo(
      rows,
      { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.36, stagger: 0.035, ease: 'power2.out', clearProps: 'opacity,transform' }
    )
  }
}

onMounted(async () => {
  await nextTick()
  if (prefersReduced || !panel.value) {
    revealRows()
    return
  }
  gsap.fromTo(overlay.value, { opacity: 0 }, { opacity: 1, duration: 0.25, ease: 'power2.out' })
  gsap.fromTo(
    panel.value,
    { xPercent: 100 },
    { xPercent: 0, duration: 0.34, ease: 'power3.out', onComplete: revealRows }
  )
})

function requestClose() {
  if (closing.value) return
  closing.value = true
  if (prefersReduced || !panel.value) {
    emit('close')
    return
  }
  gsap.to(overlay.value, { opacity: 0, duration: 0.26, ease: 'power2.in' })
  gsap.to(panel.value, {
    xPercent: 100,
    duration: 0.28,
    ease: 'power3.in',
    onComplete: () => emit('close')
  })
}

onBeforeUnmount(() => {
  gsap.killTweensOf([panel.value, overlay.value])
})
</script>

<style scoped>
.xb-scroll {
  scrollbar-gutter: stable;
}
</style>
