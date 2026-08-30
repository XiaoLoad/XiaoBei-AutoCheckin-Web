<template>
  <!-- 移动端：纵向布局，账号树限高收纳在顶部（先选账号任务，编辑器在下方） -->
  <div class="flex flex-col gap-4 lg:min-h-0 lg:flex-1 lg:flex-row">
    <!-- 左：账号 → 任务 树（搜索 + 折叠，应对账号过多） -->
    <aside class="flex w-full shrink-0 flex-col overflow-hidden rounded-2xl dash-card lg:max-h-none lg:w-60 xl:w-64">
      <div class="shrink-0 space-y-2 border-b border-ink/5 p-2">
        <div class="flex items-center gap-2 rounded-lg bg-cloud px-2.5">
          <Icon name="search" :size="14" class="shrink-0 text-ink-muted" />
          <input
            v-model="search"
            type="text"
            placeholder="搜索账号…"
            class="w-full bg-transparent py-2 text-sm text-ink outline-none placeholder:text-ink-muted"
          />
        </div>
        <div class="flex items-center justify-between px-1">
          <span class="text-[11px] text-ink-muted">{{ filtered.length }} 个账号</span>
          <div class="flex gap-2 text-[11px]">
            <button type="button" class="text-brand hover:underline" @click="expandAll">展开</button>
            <button type="button" class="text-brand hover:underline" @click="collapseAll">收起</button>
          </div>
        </div>
      </div>

      <div class="p-2 lg:flex-1 lg:min-h-0 lg:overflow-auto">
        <p v-if="filtered.length === 0" class="px-2 py-8 text-center text-xs text-ink-muted">未找到匹配账号</p>
        <div v-for="a in filtered" :key="a.id" class="mb-1">
          <button
            type="button"
            class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm font-medium text-ink-soft transition hover:bg-cloud"
            @click="toggle(a.id)"
          >
            <Icon :name="isOpen(a.id) ? 'chevron-down' : 'chevron-right'" :size="14" class="shrink-0 text-ink-muted" />
            <Icon name="user" :size="15" class="shrink-0" />
            <span class="min-w-0 flex-1 truncate">{{ a.name }}</span>
            <span
              class="shrink-0 rounded-full px-1.5 py-0.5 text-[10px]"
              :class="a.status === 'enabled' ? 'bg-success/10 text-success' : 'bg-ink/10 text-ink-muted'"
            >{{ a.status === 'enabled' ? '启用' : '停用' }}</span>
          </button>
          <div v-if="isOpen(a.id)" class="mt-0.5 space-y-0.5">
            <button
              v-for="t in a.tasks"
              :key="t.key"
              type="button"
              class="ml-5 flex w-[calc(100%-1.25rem)] items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition"
              :class="isSelected(a.id, t.type) ? 'bg-brand/10 text-brand' : 'text-ink-soft hover:bg-cloud'"
              @click="pick(a.id, t.type)"
            >
              <Icon name="box" :size="14" class="shrink-0" />
              <span class="truncate">{{ t.label }}</span>
              <span
                class="ml-auto shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium"
                :class="t.enabled ? 'bg-success/10 text-success' : 'bg-ink/10 text-ink-muted'"
              >{{ t.enabled ? '已启用' : '未启用' }}</span>
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- 右：编辑器 -->
    <div class="xb-scroll overflow-auto lg:flex-1 lg:min-h-0">
      <div v-if="!store.taskConfig" class="dash-card flex min-h-[300px] items-center justify-center text-ink-muted">请选择左侧账号任务</div>
      <template v-else>
        <div class="mb-3 space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 class="text-sm font-semibold text-ink">{{ accountName }} · {{ typeLabel }}</h3>
              <p class="mt-0.5 text-xs text-ink-muted">{{ headerHint }}</p>
            </div>
            <div class="flex items-center gap-2">
              <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium" :class="store.taskStatus.cls">
                <span class="h-1.5 w-1.5 rounded-full bg-current" />{{ store.taskStatus.text }}
              </span>
              <!-- 主按钮状态机：未启用→启用定时任务；运行中有改动→保存修改；运行中无改动→暂停调度 -->
              <button
                v-if="!taskState.enabled"
                type="button"
                class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
                :disabled="store.saving || !cfgComplete"
                @click="onEnable"
              >
                <Icon name="clock" :size="14" />启用定时任务
              </button>
              <button
                v-else-if="store.isDirty"
                type="button"
                class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
                :disabled="store.saving"
                @click="onSaveConfig"
              >
                <Icon name="check" :size="14" />保存修改
              </button>
              <button
                v-else
                type="button"
                class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-ink/70 px-4 text-sm font-medium text-white transition hover:bg-ink disabled:opacity-50"
                :disabled="store.saving"
                @click="onPause"
              >
                <Icon name="x-circle" :size="14" />暂停调度
              </button>
            </div>
          </div>

          <!-- 启用前置提示：配置必填项不完整 -->
          <div v-if="!taskState.enabled && !cfgComplete" class="flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-ink-soft">
            <Icon name="alert" :size="14" class="mt-0.5 shrink-0 text-warning" />
            <span>启用前请先完善必填项：{{ blockHint }}。补全后保存，再点「启用定时任务」。</span>
          </div>

          <!-- 配置套选择（仅本地选择/预览）+ 手动套用 + 次要编辑动作 -->
          <div class="flex flex-wrap items-center gap-2 rounded-lg bg-cloud/50 px-3 py-2">
            <span class="shrink-0 text-xs text-ink-soft">配置套</span>
            <div class="w-48">
              <BaseSelect v-model="bindPick" :options="store.setOptions" :searchable="true" size="sm" placeholder="选择配置套" />
            </div>
            <button
              type="button"
              class="inline-flex h-8 shrink-0 items-center gap-1 rounded-lg border border-ink/10 px-3 text-sm text-ink-soft transition hover:bg-cloud disabled:opacity-40"
              :disabled="!bindPick || (bindPick === (taskState.configSetId || '') && store.taskAlignedWithSource) || store.saving"
              @click="onBindApply"
            >
              <Icon name="copy" :size="13" />套用
            </button>
            <span class="mx-0.5 h-5 w-px bg-ink/10" />
            <button
              type="button"
              class="inline-flex h-8 shrink-0 items-center gap-1 rounded-lg px-2.5 text-sm text-ink-soft transition hover:bg-cloud disabled:opacity-40"
              :disabled="store.saving || !store.isDirty"
              @click="store.resetTaskConfig"
            >
              <Icon name="trash" :size="13" />重置
            </button>
            <button
              v-if="!taskState.enabled"
              type="button"
              class="inline-flex h-8 shrink-0 items-center gap-1 rounded-lg px-2.5 text-sm text-ink-soft transition hover:bg-cloud disabled:opacity-40"
              :disabled="store.saving || !store.isDirty"
              :title="`保存到「${saveTargetName}」`"
              @click="onSaveConfig"
            >
              <Icon name="check" :size="13" />保存
            </button>
            <span class="ml-auto text-[11px] text-ink-muted">{{ bindHint }}</span>
          </div>
        </div>

        <MasonryGrid>
          <TimeSection :config="store.taskConfig" :required="true" :error="store.formErrors.time" />
          <LocationSection :config="store.taskConfig" :required="true" :error="store.formErrors.location" />
          <RemarkSection :config="store.taskConfig" :required="true" :error="store.formErrors.remarks" />
          <ImageSection :config="store.taskConfig" />
          <PushSection :config="store.taskConfig" />
          <AdvancedSection :config="store.taskConfig" />
        </MasonryGrid>
      </template>
    </div>

    <!-- 保存覆盖确认：已启用任务保存将立即覆盖运行中的配置 -->
    <div
      v-if="showSaveConfirm"
      class="fixed inset-0 z-40 flex items-center justify-center bg-black/30 px-4 backdrop-blur-sm"
      @click.self="showSaveConfirm = false"
    >
      <div class="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl">
        <h3 class="text-base font-semibold text-ink">任务已启用</h3>
        <p class="mt-2 text-sm leading-relaxed text-ink-muted">该定时任务当前正在运行，保存将覆盖其配置并立即生效。确定继续保存吗？</p>
        <div class="mt-5 flex items-center justify-end gap-2">
          <button type="button" class="h-9 rounded-lg px-4 text-sm font-medium text-ink-muted transition hover:bg-cloud" @click="showSaveConfirm = false">取消</button>
          <button type="button" class="h-9 rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark" @click="confirmSave">确定保存</button>
        </div>
      </div>
    </div>

    <!-- 换绑确认：运行中的任务换绑立即生效 -->
    <div
      v-if="showBindConfirm"
      class="fixed inset-0 z-40 flex items-center justify-center bg-black/30 px-4 backdrop-blur-sm"
      @click.self="showBindConfirm = false"
    >
      <div class="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl">
        <h3 class="text-base font-semibold text-ink">换绑配置套</h3>
        <p class="mt-2 text-sm leading-relaxed text-ink-muted">任务正在运行，换绑后立即按新配置套执行。确定继续吗？</p>
        <div class="mt-5 flex items-center justify-end gap-2">
          <button type="button" class="h-9 rounded-lg px-4 text-sm font-medium text-ink-muted transition hover:bg-cloud" @click="showBindConfirm = false">取消</button>
          <button type="button" class="h-9 rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark" @click="confirmBind">确定换绑</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, reactive } from 'vue'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { useSchedulesStore } from '@/stores/schedules'
import { toast } from '@/utils/toast'
import TimeSection from '@/components/signconfig/sections/TimeSection.vue'
import LocationSection from '@/components/signconfig/sections/LocationSection.vue'
import RemarkSection from '@/components/signconfig/sections/RemarkSection.vue'
import ImageSection from '@/components/signconfig/sections/ImageSection.vue'
import PushSection from '@/components/signconfig/sections/PushSection.vue'
import AdvancedSection from '@/components/signconfig/sections/AdvancedSection.vue'
import MasonryGrid from '@/components/signconfig/MasonryGrid.vue'

const store = useSignConfigStore()
// 配置套变更需同步刷新定时任务视图（卡片的「下一次执行」取自任务实例，而非配置套）
const schedulesStore = useSchedulesStore()
async function refreshSchedulesView() {
  try {
    await schedulesStore.load()
  } catch (e) {
    /* 当前不在定时任务页时也无需刷新 */
  }
}

// ── 左树：搜索 + 折叠 ──
const search = ref('')
const expanded = reactive({})

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return store.accountTree
  return store.accountTree.filter((a) => a.name.toLowerCase().includes(q))
})

function isOpen(id) {
  return !!expanded[id]
}
function isSelected(aid, type) {
  return store.selectedAccountId === aid && store.selectedTaskType === type
}
function toggle(id) {
  expanded[id] = !expanded[id]
}
function expandAll() {
  store.accounts.forEach((a) => (expanded[a.id] = true))
}
function collapseAll() {
  store.accounts.forEach((a) => (expanded[a.id] = false))
}
function pick(aid, type) {
  store.selectTask(aid, type)
  expanded[aid] = true
}

// 选中账号自动展开，确保可见
watch(
  () => store.selectedAccountId,
  (id) => {
    if (id) expanded[id] = true
  },
  { immediate: true }
)

// ── 右编辑器：配置套回填 ──
const accountName = computed(() => store.accounts.find((a) => a.id === store.selectedAccountId)?.name || '')
const typeLabel = computed(() => (store.taskTypes.find((t) => t.value === store.selectedTaskType) || {}).label || '')

// 当前任务调度实例状态（来自 store，已含 enabled）
const taskState = computed(() => store.taskScheduleState)
const hasInstance = computed(() => !!taskState.value.hasInstance)
const enabled = computed(() => !!taskState.value.enabled)
// 配置完整度：必填项是否都已填写（时间/位置/备注）
const cfgComplete = computed(() => Object.keys(store.validateConfig(store.taskConfig || {})).length === 0)
const blockHint = computed(() => Object.values(store.validateConfig(store.taskConfig || {})).join('；'))
const headerHint = computed(() =>
  enabled.value
    ? '任务运行中：保存修改立即生效，暂停后可随时再次启用'
    : '配置复制自所选配置套；保存修改将写入本任务并取消关联配置套'
)
// 保存目标：本任务自持配置（与配置套解绑，互不影响）
const saveTargetName = computed(() => '本任务（独立配置）')

// 配置套下拉：仅本地选择/预览，不自动关联；关联由「套用此配置套」显式触发
const showBindConfirm = ref(false)
const pendingBindId = ref('')
const bindPick = computed({
  get: () => store.effectiveBindSetId || '',
  set: (id) => {
    if (id) store.selectBindSet(id)
  }
})
const bindHint = computed(() =>
  hasInstance.value ? '运行中换绑需二次确认' : '选择后点「套用」将配置复制到本任务'
)
async function onBindApply() {
  if (!bindPick.value) {
    toast('请先选择配置套', 'error')
    return
  }
  if (!hasInstance.value) {
    if (await store.applyBind()) await store.load()
    await refreshSchedulesView()
    return
  }
  if (enabled.value) {
    // 运行中换绑：需二次确认
    pendingBindId.value = bindPick.value
    showBindConfirm.value = true
    return
  }
  if (await store.bindSet(bindPick.value)) await store.load()
  await refreshSchedulesView()
}
async function confirmBind() {
  showBindConfirm.value = false
  if (await store.bindSet(pendingBindId.value)) await store.load()
  await refreshSchedulesView()
}

// 启用：先落盘未保存改动（确保启用的是所见配置），再创建/绑定并开启调度
async function onEnable() {
  if (store.isDirty) await store.saveTaskConfig()
  if (await store.enableTask()) await store.load()
  await refreshSchedulesView()
}
// 暂停：仅关闭调度，保留实例与绑定
async function onPause() {
  if (await store.pauseTask()) await store.load()
  await refreshSchedulesView()
}

// 保存配置：若任务已启用，先提示覆盖确认
const showSaveConfirm = ref(false)
async function onSaveConfig() {
  if (taskState.value.hasInstance && taskState.value.enabled) {
    showSaveConfirm.value = true
    return
  }
  await store.saveTaskConfig()
  await refreshSchedulesView()
}
async function confirmSave() {
  showSaveConfirm.value = false
  await store.saveTaskConfig()
  await refreshSchedulesView()
}
</script>
