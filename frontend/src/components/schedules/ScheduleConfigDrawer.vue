<template>
  <Teleport to="body">
  <div class="fixed inset-0 z-50">
    <!-- 遮罩 -->
    <div ref="overlay" class="absolute inset-0 bg-scrim/40" @click="requestClose" />

    <!-- 右滑抽屉面板 -->
    <aside
      ref="panel"
      class="absolute right-0 top-0 flex h-full w-full max-w-2xl flex-col bg-elevated shadow-2xl"
      role="dialog"
      aria-modal="true"
      tabindex="-1"
    >
      <header class="flex shrink-0 items-center justify-between gap-3 border-b border-ink/10 px-5 py-4">
        <div class="min-w-0">
          <h3 class="text-base font-semibold text-ink">任务配置</h3>
          <p class="mt-0.5 truncate text-xs text-ink-muted">{{ schedule.accountName }} · {{ schedule.taskLabel }}</p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium" :class="signConfigStore.taskStatus.cls">
            <span class="h-1.5 w-1.5 rounded-full bg-current" />{{ signConfigStore.taskStatus.text }}
          </span>
          <button type="button" class="grid h-9 w-9 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud" aria-label="关闭" @click="requestClose">
            <Icon name="close" :size="20" />
          </button>
        </div>
      </header>

      <div class="xb-scroll flex-1 min-h-0 space-y-5 overflow-y-auto px-5 py-5 transition-opacity" :class="syncing && 'opacity-60 pointer-events-none'">
        <div v-if="!signConfigStore.taskConfig" class="rounded-xl border border-ink/10 bg-cloud/40 p-5 text-center text-sm text-ink-muted">
          该任务暂无可编辑配置，请先在「签到配置 · 账号任务配置」中绑定配置套或保存本任务配置。
        </div>

        <template v-else>
          <!-- 配置套选择 + 套用 + 重置 -->
          <section>
            <div class="mb-2.5 flex items-center gap-2">
              <span class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">配置套</span>
              <span class="h-px flex-1 bg-ink/10"></span>
            </div>
            <div class="flex flex-wrap items-center gap-2 rounded-lg bg-cloud/50 px-3 py-2.5">
              <span class="shrink-0 text-xs text-ink-soft">关联套</span>
              <div class="w-48">
                <BaseSelect v-model="bindPick" :options="signConfigStore.setOptionsFor(props.schedule.taskType)" :searchable="true" size="sm" placeholder="选择配置套" />
              </div>
              <button
                type="button"
                class="inline-flex h-8 shrink-0 items-center gap-1 rounded-lg border border-ink/10 px-3 text-sm text-ink-soft transition hover:bg-elevated disabled:opacity-40"
                :disabled="!bindPick || bindPick === (taskState.configSetId || '') || signConfigStore.saving"
                @click="onBindApply"
              >
                <Icon name="copy" :size="13" />套用
              </button>
              <span class="mx-0.5 h-5 w-px bg-ink/10" />
              <button
                type="button"
                class="inline-flex h-8 shrink-0 items-center gap-1 rounded-lg px-2.5 text-sm text-ink-soft transition hover:bg-elevated disabled:opacity-40"
                :disabled="signConfigStore.saving || !signConfigStore.isDirty"
                @click="onReset"
              >
                <Icon name="trash" :size="13" />重置
              </button>
              <span class="ml-auto text-[11px] text-ink-muted">{{ bindHint }}</span>
            </div>
            <p class="mt-2 text-xs leading-relaxed text-ink-muted">
              「套用」将所选配置套的完整配置复制到本任务（快照）。「自定义修改」后点「保存修改」：若配置与某配置套完全一致会自动关联该套，否则作为独立自定义配置保存。
            </p>
          </section>

          <!-- 配置编辑区 -->
          <section>
            <div class="mb-2.5 flex items-center gap-2">
              <span class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">配置项</span>
              <span class="h-px flex-1 bg-ink/10"></span>
            </div>
            <MasonryGrid>
              <TimeSection :config="signConfigStore.taskConfig" :required="true" :error="signConfigStore.formErrors.time" />
              <!-- 活动签到专属：课表驱动调度（按任务类型显示，寝室任务无此块） -->
              <ActivitySection
                v-if="props.schedule.taskType === 'activity'"
                :config="signConfigStore.taskConfig"
                :account-id="String(props.schedule.accountId || '')"
              />
              <LocationSection :config="signConfigStore.taskConfig" :required="true" :error="signConfigStore.formErrors.location" />
              <RemarkSection :config="signConfigStore.taskConfig" :required="true" :error="signConfigStore.formErrors.remarks" :sample-name="remarkSampleName" />
              <ImageSection :config="signConfigStore.taskConfig" :account="scheduleAccount" />
              <PushSection scope="account" :config="signConfigStore.taskConfig" :account="scheduleAccount" />
              <AdvancedSection :config="signConfigStore.taskConfig" />
            </MasonryGrid>
          </section>
        </template>
      </div>

      <footer class="flex shrink-0 items-center justify-end gap-2 border-t border-ink/10 px-5 py-4">
        <button type="button" class="inline-flex h-9 items-center rounded-lg border border-ink/10 px-4 text-sm font-medium text-ink-soft transition hover:bg-cloud" @click="requestClose">
          关闭
        </button>
        <button
          type="button"
          class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
          :disabled="!signConfigStore.taskConfig || signConfigStore.saving || !signConfigStore.isDirty"
          @click="onSaveConfig"
        >
          <Icon name="check" :size="14" />{{ signConfigStore.saving ? '保存中…' : '保存修改' }}
        </button>
      </footer>
    </aside>

    <!-- 套用确认：运行中任务换绑立即生效 -->
    <div
      v-if="showBindConfirm"
      class="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 px-4 backdrop-blur-sm"
      @click.self="showBindConfirm = false"
    >
      <div class="w-full max-w-sm rounded-2xl bg-elevated p-5 shadow-xl">
        <h3 class="text-base font-semibold text-ink">套用配置套</h3>
        <p class="mt-2 text-sm leading-relaxed text-ink-muted">任务正在运行，套用后立即按新配置套执行。确定继续吗？</p>
        <div class="mt-5 flex items-center justify-end gap-2">
          <button type="button" class="h-9 rounded-lg px-4 text-sm font-medium text-ink-muted transition hover:bg-cloud" @click="showBindConfirm = false">取消</button>
          <button type="button" class="h-9 rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark" @click="confirmBind">确定套用</button>
        </div>
      </div>
    </div>

    <!-- 保存确认：运行中任务保存将立即覆盖运行配置 -->
    <div
      v-if="showSaveConfirm"
      class="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 px-4 backdrop-blur-sm"
      @click.self="showSaveConfirm = false"
    >
      <div class="w-full max-w-sm rounded-2xl bg-elevated p-5 shadow-xl">
        <h3 class="text-base font-semibold text-ink">任务已启用</h3>
        <p class="mt-2 text-sm leading-relaxed text-ink-muted">该定时任务当前正在运行，保存将覆盖其配置并立即生效。确定继续保存吗？</p>
        <div class="mt-5 flex items-center justify-end gap-2">
          <button type="button" class="h-9 rounded-lg px-4 text-sm font-medium text-ink-muted transition hover:bg-cloud" @click="showSaveConfirm = false">取消</button>
          <button type="button" class="h-9 rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark" @click="confirmSave">确定保存</button>
        </div>
      </div>
    </div>
  </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'
import { useOverlayA11y } from '@/composables/useOverlayA11y'
import BaseSelect from '@/components/BaseSelect.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { useSchedulesStore } from '@/stores/schedules'
import { useRefreshBusStore } from '@/stores/refreshBus'
import { toast } from '@/utils/toast'
import TimeSection from '@/components/signconfig/sections/TimeSection.vue'
import ActivitySection from '@/components/signconfig/sections/ActivitySection.vue'
import LocationSection from '@/components/signconfig/sections/LocationSection.vue'
import RemarkSection from '@/components/signconfig/sections/RemarkSection.vue'
import ImageSection from '@/components/signconfig/sections/ImageSection.vue'
import PushSection from '@/components/signconfig/sections/PushSection.vue'
import AdvancedSection from '@/components/signconfig/sections/AdvancedSection.vue'
import MasonryGrid from '@/components/signconfig/MasonryGrid.vue'

const props = defineProps({
  schedule: { type: Object, required: true }
})
const emit = defineEmits(['close'])

const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const overlay = ref(null)
const panel = ref(null)
// 无障碍基线：ESC 关闭 + 初始聚焦面板 + 背景滚动锁定
useOverlayA11y(panel, requestClose)
const closing = ref(false)

const signConfigStore = useSignConfigStore()
const schedulesStore = useSchedulesStore()
const refreshBus = useRefreshBusStore()

// 抽屉冷加载中：打开时若配置 store 尚无数据需现场拉取（非静默刷新、总线只登记
// 静默分支），此处局部登记总线并在抽屉体上降透明，保证抽屉内加载有感知
const syncing = ref(false)

// 当前任务调度实例状态（来自 signConfigStore，已含 enabled / scheduleId / configSetId）
const taskState = computed(() => signConfigStore.taskScheduleState)

// 定时任务所属账号：图片策略卡的「账号视角」用它解析所在分组
const scheduleAccount = computed(
  () => signConfigStore.accounts.find((a) => a.id === String(props.schedule.accountId || '')) || null
)

// 备注预览示例姓名：当前任务所属账号的 B 平台姓名
const remarkSampleName = computed(() => scheduleAccount.value?.name || '')

// 配置套下拉：仅本地选择/预览，关联由「套用」显式触发
const bindPick = computed({
  get: () => signConfigStore.effectiveBindSetId || '',
  set: (id) => {
    if (id) signConfigStore.selectBindSet(id)
  }
})
const bindHint = computed(() => {
  if (!taskState.value.hasInstance) return '套用将创建任务实例并复制配置'
  if (taskState.value.enabled) return '运行中套用需二次确认'
  return '套用将把配置复制到本任务'
})

// 打开抽屉即把 signConfigStore 指向该任务，复用其编辑副本与关联逻辑（单一真相源，与签到配置页同步）
onMounted(async () => {
  // 判据用 loaded（真正加载过）而非 loading：loading 初值为 true，
  // 直接落在定时任务页刷新时该 store 从未加载，用 !loading 判断会永不拉取
  if (!signConfigStore.loaded) {
    syncing.value = true
    try {
      await refreshBus.run(() => signConfigStore.load())
    } finally {
      syncing.value = false
    }
  }
  signConfigStore.selectTask(props.schedule.accountId, props.schedule.taskType)
  await nextTick()
  if (prefersReduced || !panel.value) return
  gsap.fromTo(overlay.value, { opacity: 0 }, { opacity: 1, duration: 0.25, ease: 'power2.out' })
  gsap.fromTo(panel.value, { xPercent: 100 }, { xPercent: 0, duration: 0.32, ease: 'power3.out' })
})

// 套用配置套（复制快照到本任务）
const showBindConfirm = ref(false)
const pendingBindId = ref('')
async function onBindApply() {
  if (!bindPick.value) {
    toast('请先选择配置套', 'error')
    return
  }
  if (!taskState.value.hasInstance) {
    if (await signConfigStore.applyBind()) await refreshSchedulesView()
    return
  }
  if (taskState.value.enabled) {
    pendingBindId.value = bindPick.value
    showBindConfirm.value = true
    return
  }
  if (await signConfigStore.bindSet(bindPick.value)) await refreshSchedulesView()
}
async function confirmBind() {
  showBindConfirm.value = false
  if (await signConfigStore.bindSet(pendingBindId.value)) await refreshSchedulesView()
}

// 重置本地草稿（以来源重新克隆）
function onReset() {
  signConfigStore.resetTaskConfig()
}

// 保存修改：自定义配置自动按 configsEqual 关联匹配的配置套，否则解绑
const showSaveConfirm = ref(false)
async function onSaveConfig() {
  if (taskState.value.hasInstance && taskState.value.enabled) {
    showSaveConfirm.value = true
    return
  }
  await doSave()
}
async function confirmSave() {
  showSaveConfirm.value = false
  await doSave()
}
async function doSave() {
  const ok = await signConfigStore.saveTaskConfigLinked(props.schedule.id, props.schedule.taskType)
  if (ok) await refreshSchedulesView()
}

// 配置套变更需同步刷新定时任务视图（卡片的「下一次执行」取自任务实例，而非配置套）；
// 经总线登记，即使该 store 在本会话尚未加载过（首载无静默分支）也有顶部进度条
async function refreshSchedulesView() {
  try {
    await refreshBus.run(() => schedulesStore.load())
  } catch (e) {
    /* 抽屉内无需强依赖 */
  }
}

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
