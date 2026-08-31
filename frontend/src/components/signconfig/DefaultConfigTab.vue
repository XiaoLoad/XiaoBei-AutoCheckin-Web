<template>
  <!-- 移动端：纵向布局，配置套列表收纳为顶部切换器（重命名/删除等管理动作在桌面端进行） -->
  <div ref="root" class="flex flex-col gap-4 lg:min-h-0 lg:flex-1 lg:flex-row">
    <!-- 左：配置套列表（多项命名模板） -->
    <aside class="hidden w-56 shrink-0 flex-col overflow-hidden rounded-2xl dash-card lg:flex xl:w-60">
      <div class="flex shrink-0 items-center justify-between border-b border-ink/5 p-3">
        <span class="text-sm font-semibold text-ink">我的配置套</span>
        <button
          type="button"
          class="inline-flex h-7 items-center gap-1 rounded-lg bg-brand px-2.5 text-xs font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
          :disabled="store.saving"
          @click="store.createConfigSet()"
        >
          <Icon name="plus" :size="13" />新建
        </button>
      </div>
      <div class="xb-scroll flex-1 min-h-0 overflow-auto p-2">
        <p v-if="store.userConfigSets.length === 0" class="px-1 py-8 text-center text-xs text-ink-muted">暂无配置套<br />点击右上角新建</p>
        <div v-for="s in store.userConfigSets" :key="s.id" class="xb-set-item mb-1">
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
              class="min-w-0 flex-1 rounded-md border border-brand/40 bg-white px-2 py-0.5 text-sm text-ink outline-none focus:ring-2 focus:ring-brand/10"
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
      </div>
    </aside>

    <!-- 右：选中配置套的六段编辑器 -->
    <div class="xb-scroll overflow-auto lg:flex-1 lg:min-h-0">
      <!-- 移动端配置套切换器（桌面端见左侧列表） -->
      <div class="mb-3 flex shrink-0 items-center gap-2 lg:hidden">
        <div class="min-w-0 flex-1">
          <BaseSelect v-model="store.activeSetId" :options="setOptions" :searchable="true" size="sm" placeholder="选择配置套" />
        </div>
        <button
          type="button"
          class="inline-flex h-9 shrink-0 items-center gap-1 rounded-lg bg-brand px-3 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
          :disabled="store.saving"
          @click="store.createConfigSet()"
        >
          <Icon name="plus" :size="13" />新建
        </button>
      </div>
      <div v-if="!store.activeSet" class="dash-card flex min-h-[300px] items-center justify-center text-ink-muted">请先在左侧创建配置套</div>
      <template v-else>
        <div class="xb-reveal mb-3 flex flex-wrap items-center justify-between gap-2">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="text-sm font-semibold text-ink">正在编辑：{{ store.activeSet.name }}</h3>
              <button
                type="button"
                class="inline-flex shrink-0 items-center gap-1 rounded-full border border-brand/20 bg-brand/10 px-2.5 py-1 text-[11px] font-medium leading-none text-brand transition hover:border-brand/30 hover:bg-brand/20 active:scale-95"
                :title="`当前配置套有 ${activeSetSummary.accountsCount} 个账号使用、${activeSetSummary.instancesCount} 个任务实例，点击查看明细`"
                @click="openUsage(store.activeSet.id)"
              >
                {{ activeSetSummary.accountsCount }} 个账号使用 · {{ activeSetSummary.instancesCount }} 个任务实例
              </button>
            </div>
            <p class="text-xs text-ink-muted">配置套是一份完整模板；在「账号任务配置」里可指定某任务回填此套。</p>
          </div>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="inline-flex h-9 items-center gap-1.5 rounded-lg border border-brand/30 px-4 text-sm font-medium text-brand transition hover:bg-brand/10 disabled:opacity-50"
              :disabled="store.saving"
              @click="showApplyAll = true"
            >
              <Icon name="send" :size="14" />应用全部
            </button>
            <button
              type="button"
              class="inline-flex h-9 items-center gap-1.5 rounded-lg border border-ink/10 px-4 text-sm font-medium text-ink-soft transition hover:bg-cloud disabled:opacity-50"
              :disabled="store.saving"
              @click="store.resetActiveSetConfig"
            >
              <Icon name="trash" :size="14" />清空填写
            </button>
            <button
              type="button"
              class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
              :disabled="store.saving || !store.activeSetDirty"
              :title="store.activeSetDirty ? '' : '未修改任何配置项，无需保存'"
              @click="store.saveActiveSet"
            >
              <Icon name="check" :size="14" />{{ store.saving ? '保存中…' : '保存配置套' }}
            </button>
          </div>
        </div>

        <div class="xb-reveal rounded-xl border-l-4 border-brand/30 bg-brand/5 px-4 py-3 text-xs leading-relaxed text-ink-soft">
          这是<strong>你的配置套（命名模板）</strong>。不同 B 账号批次时间规律不同（如一批周三至周五、一批仅周日），可分别建套；填写账号任务时再引用对应套回填，避免重复配置。改完点右上角保存。
        </div>

        <MasonryGrid class="mt-4">
          <TimeSection :config="store.activeSet.config" :required="true" :error="store.formErrors.time" />
          <LocationSection :config="store.activeSet.config" :required="true" :error="store.formErrors.location" />
          <RemarkSection :config="store.activeSet.config" :required="true" :error="store.formErrors.remarks" />
          <ImageSection :config="store.activeSet.config" />
          <PushSection :config="store.activeSet.config" />
          <AdvancedSection :config="store.activeSet.config" />
        </MasonryGrid>
      </template>
    </div>

    <!-- 应用全部：二次确认弹窗 -->
    <ConfirmModal
      v-model="showApplyAll"
      icon="send"
      title="应用配置套到全部关联任务"
      :confirm-text="store.saving ? '处理中…' : '确认应用全部'"
      :confirming="store.saving"
      @confirm="onApplyAllConfirm"
    >
      <p>将把当前配置套「<strong>{{ store.activeSet?.name }}</strong>」的完整配置<strong>覆盖写入</strong>所有已套用该套的账号任务配置（直接替换其现有配置，不可撤销）。</p>
      <p class="mt-2">仅影响「已套用」状态的任务；跟随配置套的任务会实时生效，无需此操作。</p>
    </ConfirmModal>

    <!-- 套用明细：哪些账号的哪些任务套用了当前配置套 -->
    <ConfigSetUsageDrawer v-if="usageSetId" :set-id="usageSetId" @close="usageSetId = null" />
  </div>
</template>

<script setup>
import { computed, ref, onActivated, onUnmounted, watch, nextTick } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { toast } from '@/utils/toast'
import TimeSection from '@/components/signconfig/sections/TimeSection.vue'
import LocationSection from '@/components/signconfig/sections/LocationSection.vue'
import RemarkSection from '@/components/signconfig/sections/RemarkSection.vue'
import ImageSection from '@/components/signconfig/sections/ImageSection.vue'
import PushSection from '@/components/signconfig/sections/PushSection.vue'
import AdvancedSection from '@/components/signconfig/sections/AdvancedSection.vue'
import MasonryGrid from '@/components/signconfig/MasonryGrid.vue'
import ConfigSetUsageDrawer from '@/components/signconfig/ConfigSetUsageDrawer.vue'

const store = useSignConfigStore()

// 移动端配置套切换器选项
const setOptions = computed(() => store.userConfigSets.map((s) => ({ label: s.name, value: s.id })))

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

// —— 应用全部：二次确认 ——
const showApplyAll = ref(false)
function onApplyAllConfirm() {
  if (!store.activeSet) return
  store.applyConfigSetToAll(store.activeSet.id).finally(() => {
    showApplyAll.value = false
  })
}

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
