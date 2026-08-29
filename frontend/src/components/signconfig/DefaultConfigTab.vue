<template>
  <div ref="root" class="flex flex-1 min-h-0 gap-4">
    <!-- 左：配置套列表（多项命名模板） -->
    <aside class="flex w-56 shrink-0 flex-col overflow-hidden rounded-2xl dash-card xl:w-60">
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
              class="min-w-0 flex-1 truncate text-left text-sm"
              @click="store.setActiveSet(s.id)"
            >
              {{ s.name }}
            </button>
            <input
              v-else
              :ref="(el) => setRenameInput(el)"
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
    <div class="xb-scroll flex-1 min-h-0 overflow-auto">
      <div v-if="!store.activeSet" class="dash-card flex min-h-[300px] items-center justify-center text-ink-muted">请先在左侧创建配置套</div>
      <template v-else>
        <div class="xb-reveal mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 class="text-sm font-semibold text-ink">正在编辑：{{ store.activeSet.name }}</h3>
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
  </div>
</template>

<script setup>
import { ref, onActivated, onUnmounted, watch, nextTick } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'
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

const store = useSignConfigStore()

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
function setRenameInput(el) {
  if (el) {
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
