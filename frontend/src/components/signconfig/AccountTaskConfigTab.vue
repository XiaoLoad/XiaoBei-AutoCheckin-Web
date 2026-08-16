<template>
  <div class="flex flex-1 min-h-0 gap-4">
    <!-- 左：账号 → 任务 树（搜索 + 折叠，应对账号过多） -->
    <aside class="flex w-60 shrink-0 flex-col overflow-hidden rounded-2xl dash-card xl:w-64">
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

      <div class="xb-scroll flex-1 min-h-0 overflow-auto p-2">
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
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- 右：编辑器 -->
    <div class="xb-scroll flex-1 min-h-0 overflow-auto">
      <div v-if="!store.taskConfig" class="dash-card flex min-h-[300px] items-center justify-center text-ink-muted">请选择左侧账号任务</div>
      <template v-else>
        <div class="mb-3 space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 class="text-sm font-semibold text-ink">{{ accountName }} · {{ typeLabel }}</h3>
              <p class="text-xs text-ink-muted">从下方六类配置中调整；也可先选一套配置套回填，再按需微调。</p>
            </div>
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="inline-flex h-9 items-center gap-1.5 rounded-lg border border-ink/10 px-4 text-sm font-medium text-ink-soft transition hover:bg-cloud disabled:opacity-50"
                :disabled="store.saving"
                @click="store.resetTaskConfig"
              >
                <Icon name="trash" :size="14" />清空填写
              </button>
              <button
                class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
                :disabled="store.saving"
                @click="store.saveTaskConfig"
              >
                <Icon name="check" :size="14" />{{ store.saving ? '保存中…' : '保存' }}
              </button>
            </div>
          </div>

          <!-- 配置套回填 + 任务状态 -->
          <div class="flex flex-wrap items-center gap-2 rounded-lg bg-cloud/50 px-3 py-2">
            <span class="text-xs text-ink-soft">配置套回填：</span>
            <div class="w-56">
              <BaseSelect v-model="applySetId" :options="store.setOptions" :searchable="true" size="sm" placeholder="选择配置套" />
            </div>
            <button
              type="button"
              class="inline-flex h-8 items-center gap-1 rounded-lg border border-ink/10 px-3 text-sm text-ink-soft transition hover:bg-cloud disabled:opacity-40"
              :disabled="!applySetId"
              @click="applySet"
            >
              <Icon name="copy" :size="13" />应用到此任务
            </button>
            <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium" :class="store.taskStatus.cls">
              <span class="h-1.5 w-1.5 rounded-full bg-current" />{{ store.taskStatus.text }}
            </span>
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
  </div>
</template>

<script setup>
import { ref, computed, watch, reactive } from 'vue'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import TimeSection from '@/components/signconfig/sections/TimeSection.vue'
import LocationSection from '@/components/signconfig/sections/LocationSection.vue'
import RemarkSection from '@/components/signconfig/sections/RemarkSection.vue'
import ImageSection from '@/components/signconfig/sections/ImageSection.vue'
import PushSection from '@/components/signconfig/sections/PushSection.vue'
import AdvancedSection from '@/components/signconfig/sections/AdvancedSection.vue'
import MasonryGrid from '@/components/signconfig/MasonryGrid.vue'

const store = useSignConfigStore()

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

const applySetId = ref('')
// 切换任务时，回填选择器默认指向该任务已关联的配置套
watch(
  () => store.taskConfigKey,
  () => {
    applySetId.value = store.taskConfig?.presetSetId || ''
  },
  { immediate: true }
)
function applySet() {
  if (applySetId.value) store.applySetToTask(applySetId.value)
}
</script>
