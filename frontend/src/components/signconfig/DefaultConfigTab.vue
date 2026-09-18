<template>
  <!-- 移动端：纵向布局，配置套列表收纳为顶部切换器（重命名/删除等管理动作在桌面端进行） -->
  <div ref="root" class="flex flex-col gap-4 lg:min-h-0 lg:flex-1 lg:flex-row">
    <!-- 左：配置套列表（多项命名模板） -->
    <aside class="hidden w-56 shrink-0 flex-col overflow-hidden rounded-2xl dash-card lg:flex xl:w-60">
      <div class="shrink-0 space-y-2 border-b border-ink/5 p-3">
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm font-semibold text-ink">我的配置套</span>
          <div class="flex gap-1">
            <button
              type="button"
              class="inline-flex h-7 items-center gap-0.5 rounded-lg border border-brand/30 bg-brand/5 px-2 text-xs font-medium text-brand transition hover:bg-brand/10 disabled:opacity-50"
              :disabled="store.saving"
              title="新建寝室签到配置套"
              @click="store.createConfigSet(null, 'dorm')"
            >
              <Icon name="plus" :size="12" />寝室
            </button>
            <button
              type="button"
              class="inline-flex h-7 items-center gap-0.5 rounded-lg border border-info/30 bg-info/5 px-2 text-xs font-medium text-info transition hover:bg-info/10 disabled:opacity-50"
              :disabled="store.saving"
              title="新建活动签到配置套"
              @click="store.createConfigSet(null, 'activity')"
            >
              <Icon name="plus" :size="12" />活动
            </button>
          </div>
        </div>
        <!-- 搜索 + 类型筛选：收纳在侧栏头部下方，配置套多时快速定位 -->
        <div class="flex items-center gap-2 rounded-lg bg-cloud px-2.5">
          <Icon name="search" :size="14" class="shrink-0 text-ink-muted" />
          <input
            v-model="setSearch"
            type="text"
            placeholder="搜索配置套…"
            aria-label="搜索配置套"
            class="w-full bg-transparent py-2 text-sm text-ink outline-none placeholder:text-ink-muted"
          />
          <button
            v-if="setSearch"
            type="button"
            class="shrink-0 text-ink-muted transition hover:text-ink-soft"
            aria-label="清空搜索"
            @click="setSearch = ''"
          >
            <Icon name="close" :size="13" />
          </button>
        </div>
        <div class="flex items-center justify-between gap-2">
          <div class="inline-flex rounded-lg bg-cloud p-0.5" role="group" aria-label="按类型筛选">
            <button
              v-for="f in typeFilters"
              :key="f.value"
              type="button"
              class="rounded-md px-2.5 py-1 text-[11px] font-medium transition"
              :class="setTypeFilter === f.value ? 'bg-elevated text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
              @click="setTypeFilter = f.value"
            >
              {{ f.label }}
            </button>
          </div>
          <span class="text-[11px] text-ink-muted">{{ filteredCount }} 个</span>
        </div>
      </div>
      <div class="xb-scroll flex-1 min-h-0 overflow-auto p-2">
        <p v-if="store.userConfigSets.length === 0" class="px-1 py-8 text-center text-xs text-ink-muted">暂无配置套<br />点击右上角新建</p>
        <p v-else-if="filteredCount === 0" class="px-1 py-8 text-center text-xs text-ink-muted">
          没有匹配的配置套<br />试试调整类型筛选或搜索关键词
        </p>
        <template v-for="group in setGroups" :key="group.type">
          <p class="px-2 pb-1 pt-2 text-[11px] font-medium text-ink-muted">{{ group.label }}</p>
          <div v-for="s in group.items" :key="s.id" class="xb-set-item mb-1">
          <div
            class="flex items-center gap-1 rounded-lg px-2 py-1.5 transition"
            :class="store.activeSetId === s.id ? 'bg-brand/10 text-brand' : 'text-ink-soft hover:bg-cloud'"
          >
            <button
              v-if="renamingId !== s.id"
              type="button"
              class="flex min-w-0 flex-1 items-center gap-1.5 text-left text-sm"
              @click="store.setActiveSet(s.id)"
            >
              <span class="min-w-0 flex-1 truncate">{{ s.name }}</span>
            </button>
            <!-- 套用明细入口：点击查看哪些账号的哪些任务套用了此套（纯数字徽标，与名称垂直居中） -->
            <button
              v-if="renamingId !== s.id && setUsage[s.id]"
              type="button"
              class="inline-flex h-5 min-w-[20px] shrink-0 items-center justify-center rounded-full bg-brand/10 px-1.5 text-[10px] font-semibold leading-none text-brand transition hover:bg-brand/20 active:scale-95"
              :title="`${setUsage[s.id]} 个账号套用此配置套，点击查看明细`"
              @click.stop="openUsage(s.id)"
            >
              {{ setUsage[s.id] }}
            </button>
            <input
              v-if="renamingId === s.id"
              :ref="(el) => setRenameInput(el, s.id)"
              v-model="renameText"
              type="text"
              class="min-w-0 flex-1 rounded-md border border-brand/40 bg-elevated px-2 py-0.5 text-sm text-ink outline-none focus:ring-2 focus:ring-brand/10"
              @keyup.enter="commitRename(s)"
              @keyup.esc="cancelRename"
              @blur="commitRename(s)"
            />
            <button
              v-if="renamingId !== s.id"
              type="button"
              class="shrink-0 rounded p-1 text-ink-muted transition hover:text-ink-soft"
              title="重命名"
              @click="startRename(s)"
            >
              <Icon name="edit" :size="13" />
            </button>
            <button
              v-else
              type="button"
              class="shrink-0 rounded p-1 text-brand transition hover:bg-brand/10"
              title="确认重命名"
              @click="commitRename(s)"
            >
              <Icon name="check" :size="13" />
            </button>
            <button
              type="button"
              class="shrink-0 rounded p-1 text-ink-muted transition hover:text-danger"
              :title="store.userConfigSets.length <= 1 ? '至少保留一个配置套，无法删除' : '删除'"
              @click="onDelete(s)"
            >
              <Icon name="trash" :size="13" />
            </button>
          </div>
        </div>
        </template>
      </div>
    </aside>

    <!-- 右：选中配置套的六段编辑器 -->
    <!-- 右：工作台画布——编辑区整体收纳进一张大卡，头部/提示/瀑布流皆为画布内容 -->
    <div class="dash-card xb-scroll overflow-auto p-4 sm:p-5 lg:flex-1 lg:min-h-0">
      <!-- 移动端配置套切换器（桌面端见左侧列表）；带类型前缀防误选 -->
      <div class="mb-3 flex shrink-0 items-center gap-2 lg:hidden">
        <div class="min-w-0 flex-1">
          <BaseSelect v-model="store.activeSetId" :options="setOptions" :searchable="true" size="sm" placeholder="选择配置套" />
        </div>
        <button
          type="button"
          class="inline-flex h-9 shrink-0 items-center gap-1 rounded-lg border border-brand/30 bg-brand/5 px-2.5 text-xs font-medium text-brand transition hover:bg-brand/10 disabled:opacity-50"
          :disabled="store.saving"
          title="新建寝室签到配置套"
          @click="store.createConfigSet(null, 'dorm')"
        >
          <Icon name="plus" :size="12" />寝室
        </button>
        <button
          type="button"
          class="inline-flex h-9 shrink-0 items-center gap-1 rounded-lg border border-info/30 bg-info/5 px-2.5 text-xs font-medium text-info transition hover:bg-info/10 disabled:opacity-50"
          :disabled="store.saving"
          title="新建活动签到配置套"
          @click="store.createConfigSet(null, 'activity')"
        >
          <Icon name="plus" :size="12" />活动
        </button>
      </div>
      <div v-if="!store.activeSet" class="flex min-h-[300px] items-center justify-center text-ink-muted">请先在左侧创建配置套</div>
      <template v-else>
        <div class="xb-reveal mb-3 flex flex-wrap items-center justify-between gap-2">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="min-w-0 max-w-full truncate text-sm font-semibold text-ink">正在编辑：{{ store.activeSet.name }}</h3>
              <span
                class="inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-medium"
                :class="isActivitySet ? 'bg-info/10 text-info' : 'bg-success/10 text-success'"
              >{{ isActivitySet ? '活动签到套' : '寝室签到套' }}</span>
              <button
                type="button"
                class="inline-flex shrink-0 items-center gap-1 rounded-full border border-brand/20 bg-brand/10 px-2.5 py-1 text-[11px] font-medium leading-none text-brand transition hover:border-brand/30 hover:bg-brand/20 active:scale-95"
                :title="`当前配置套有 ${activeSetSummary.accountsCount} 个账号使用、${activeSetSummary.instancesCount} 个任务实例，点击查看明细`"
                @click="openUsage(store.activeSet.id)"
              >
                {{ activeSetSummary.accountsCount }} 个账号使用 · {{ activeSetSummary.instancesCount }} 个任务实例
              </button>
            </div>
            <p class="text-xs text-ink-muted">
              配置套是一份完整模板；在「账号任务配置」里可指定某任务回填此套。{{ isActivitySet ? '活动套中「定时签到时间」用作每日兜底查询时刻。' : '' }}
            </p>
          </div>
          <!-- 动作组：shrink-0 + nowrap 保证按钮永不内部折行；窄屏时整组换行到下一行 -->
          <div class="flex shrink-0 flex-wrap items-center gap-2">
            <button
              type="button"
              class="inline-flex h-9 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-brand/30 px-4 text-sm font-medium text-brand transition hover:bg-brand/10 disabled:opacity-50"
              :disabled="store.saving"
              @click="showApplyDrawer = true"
            >
              <Icon name="send" :size="14" />批量应用
            </button>
            <button
              type="button"
              class="inline-flex h-9 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-ink/10 px-4 text-sm font-medium text-ink-soft transition hover:bg-cloud disabled:opacity-50"
              :disabled="store.saving"
              @click="store.resetActiveSetConfig"
            >
              <Icon name="trash" :size="14" />清空填写
            </button>
            <button
              type="button"
              class="inline-flex h-9 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
              :disabled="store.saving || !store.activeSetDirty"
              :title="store.activeSetDirty ? '' : '未修改任何配置项，无需保存'"
              @click="store.saveActiveSet"
            >
              <Icon name="check" :size="14" />{{ store.saving ? '保存中…' : '保存配置套' }}
            </button>
          </div>
        </div>

        <!-- 提示条：统一信息条材质（图标 + 品牌淡底），与账号任务配置页同款 -->
        <div class="xb-reveal flex items-start gap-2 rounded-xl bg-brand/5 px-3.5 py-2.5 text-xs leading-relaxed text-ink-soft">
          <Icon name="info" :size="14" class="mt-0.5 shrink-0 text-brand" />
          <span>这是<strong>你的配置套（命名模板）</strong>。不同 B 账号批次时间规律不同（如一批周三至周五、一批仅周日），可分别建套；填写账号任务时再引用对应套回填，避免重复配置。改完点右上角保存。</span>
        </div>

        <MasonryGrid class="mt-4">
          <TimeSection :config="store.activeSet.config" :required="true" :error="store.formErrors.time" />
          <!-- 活动调度策略仅活动签到套可见：寝室套无此块，语义干净不误导 -->
          <ActivitySection v-if="isActivitySet" :config="store.activeSet.config" />
          <LocationSection :config="store.activeSet.config" :required="true" :error="store.formErrors.location" />
          <RemarkSection :config="store.activeSet.config" :required="true" :error="store.formErrors.remarks" :sample-name="remarkSampleName" />
          <ImageSection :config="store.activeSet.config" />
          <PushSection scope="set" :config="store.activeSet.config" />
          <AdvancedSection :config="store.activeSet.config" />
        </MasonryGrid>
      </template>
    </div>

    <!-- 批量应用：右滑抽屉，勾选账号任务批量套用 / 全部应用 -->
    <ConfigSetApplyDrawer v-if="showApplyDrawer && store.activeSet" :set-id="store.activeSet.id" @close="showApplyDrawer = false" />

    <!-- 套用明细：哪些账号的哪些任务套用了当前配置套 -->
    <ConfigSetUsageDrawer v-if="usageSetId" :set-id="usageSetId" @close="usageSetId = null" />
  </div>
</template>

<script setup>
import { computed, ref, onActivated, onUnmounted, watch, nextTick } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { taskTypeMeta } from '@/utils/accountType'
import { toast } from '@/utils/toast'
import TimeSection from '@/components/signconfig/sections/TimeSection.vue'
import ActivitySection from '@/components/signconfig/sections/ActivitySection.vue'
import LocationSection from '@/components/signconfig/sections/LocationSection.vue'
import RemarkSection from '@/components/signconfig/sections/RemarkSection.vue'
import ImageSection from '@/components/signconfig/sections/ImageSection.vue'
import PushSection from '@/components/signconfig/sections/PushSection.vue'
import AdvancedSection from '@/components/signconfig/sections/AdvancedSection.vue'
import MasonryGrid from '@/components/signconfig/MasonryGrid.vue'
import ConfigSetUsageDrawer from '@/components/signconfig/ConfigSetUsageDrawer.vue'
import ConfigSetApplyDrawer from '@/components/signconfig/ConfigSetApplyDrawer.vue'

const store = useSignConfigStore()

// 移动端配置套切换器选项（带类型前缀防误选）
const setOptions = computed(() => store.userConfigSets.map((s) => ({
  label: `${taskTypeMeta(s.taskType).short} · ${s.name}`,
  value: s.id
})))

// ── 侧栏搜索 + 类型筛选（组合过滤，纯前端派生） ──
const setSearch = ref('')
const setTypeFilter = ref('all')
const typeFilters = [
  { value: 'all', label: '全部' },
  { value: 'dorm', label: '寝室' },
  { value: 'activity', label: '活动' }
]
const setGroups = computed(() => {
  const q = setSearch.value.trim().toLowerCase()
  const t = setTypeFilter.value
  const match = (s) => (t === 'all' || s.taskType === t) && (!q || s.name.toLowerCase().includes(q))
  return [
    { type: 'dorm', label: '寝室签到', items: store.userConfigSets.filter((s) => s.taskType !== 'activity' && match(s)) },
    { type: 'activity', label: '活动签到', items: store.userConfigSets.filter((s) => s.taskType === 'activity' && match(s)) },
  ].filter((g) => g.items.length)
})
const filteredCount = computed(() => setGroups.value.reduce((n, g) => n + g.items.length, 0))

// 配置套分组（寝室签到 / 活动签到）：编辑器按类型渲染区块，寝室套不含活动调度卡片
const isActivitySet = computed(() => store.activeSet?.taskType === 'activity')

// 套用明细抽屉：点击徽标查看哪些账号的哪些任务套用了某配置套
const usageSetId = ref('')
function openUsage(setId) {
  usageSetId.value = setId
}

// —— 套用数量：引用各配置套的账号数（scheduleBindings key 为 `${accountId}:${taskType}`，
//     同账号寝/活两实例按账号去重），供列表徽标与编辑头部展示，方便改套前评估影响面 ——
const setUsage = computed(() => {
  const bySet = {}
  for (const [key, b] of Object.entries(store.scheduleBindings || {})) {
    if (!b || b.configSetId == null) continue
    const accId = String(key).split(':')[0]
    bySet[b.configSetId] = bySet[b.configSetId] || new Set()
    bySet[b.configSetId].add(accId)
  }
  const out = {}
  for (const [setId, accounts] of Object.entries(bySet)) out[setId] = accounts.size
  return out
})
const activeSetUsage = computed(() => (store.activeSet ? setUsage.value[store.activeSet.id] || 0 : 0))
const activeSetSummary = computed(() =>
  store.activeSet ? store.usageSummaryOf(store.activeSet.id) : { accountsCount: 0, instancesCount: 0 }
)

// 备注预览示例姓名：取当前配置套首个绑定账号的 B 平台姓名（未绑定任何账号时回落到首个账号）
const remarkSampleName = computed(() => {
  if (store.activeSet) {
    const usage = store.usageDetailOf(store.activeSet.id)
    if (usage.length && usage[0].accountName) return usage[0].accountName
  }
  return store.accounts[0]?.name || ''
})

// —— 批量应用：右滑抽屉替代原「应用全部」弹窗 ——
const showApplyDrawer = ref(false)

// —— 重命名：原地行内编辑，不再在下方弹出独立输入框 ——
const renamingId = ref('')
const renameText = ref('')
function setRenameInput(el, id) {
  // [重命名修复] 函数式 ref 在每次重渲染（如键入触发 v-model 更新）时都会重新执行，
  // 无守卫的 select() 会把已键入内容重新全选、被下一个字符覆盖（表现为输入被清空重写）。
  // 仅在"该行正处重命名态且输入框尚未聚焦"时聚焦并全选一次。
  if (el && renamingId.value === id && document.activeElement !== el) {
    el.focus()
    el.select()
  }
}
function startRename(s) {
  renamingId.value = s.id
  renameText.value = s.name
}
function cancelRename() {
  renamingId.value = ''
}
function commitRename(s) {
  if (renamingId.value !== s.id) return
  const name = renameText.value.trim()
  if (name && name !== s.name) store.renameConfigSet(s.id, name)
  renamingId.value = ''
}
// 仅剩一个配置套时禁止删除并给出提示（复用全局 Toast 组件）
function onDelete(s) {
  if (store.userConfigSets.length <= 1) {
    toast('至少保留一个配置套，无法删除', 'warning')
    return
  }
  store.deleteConfigSet(s.id)
}

// —— 入场动画（GSAP）：侧栏列表、右栏标题/说明、六段卡片错峰淡入 ——
const root = ref(null)
let ctx = null
const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
function reveal() {
  if (prefersReduced || !root.value) return
  if (ctx) ctx.revert()
  ctx = gsap.context(() => {
    const tl = gsap.timeline({ defaults: { ease: 'power2.out' } })
    const listItems = gsap.utils.toArray('.xb-set-item')
    const heads = gsap.utils.toArray('.xb-reveal')
    const cards = gsap.utils.toArray('.xb-masonry-item')
    if (listItems.length) tl.fromTo(listItems, { opacity: 0, x: -12 }, { opacity: 1, x: 0, duration: 0.4, stagger: 0.06, clearProps: 'opacity,transform' }, 0)
    if (heads.length) tl.fromTo(heads, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.45, stagger: 0.08, clearProps: 'opacity,transform' }, 0.05)
    if (cards.length) tl.fromTo(cards, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.5, stagger: 0.06, clearProps: 'opacity,transform' }, 0.1)
  }, root.value)
}
onActivated(async () => {
  await nextTick()
  reveal()
})
// 切换配置套时右栏内容整体刷新，重新播放错峰入场
watch(
  () => store.activeSetId,
  async () => {
    await nextTick()
    reveal()
  }
)
onUnmounted(() => {
  if (ctx) ctx.revert()
})
</script>
