<template>
  <div class="flex flex-1 min-h-0 gap-4">
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
        <div v-for="s in store.userConfigSets" :key="s.id" class="mb-1">
          <div
            class="flex items-center gap-1 rounded-lg px-2 py-1.5 transition"
            :class="store.activeSetId === s.id ? 'bg-brand/10 text-brand' : 'text-ink-soft hover:bg-cloud'"
          >
            <button type="button" class="min-w-0 flex-1 truncate text-left text-sm" @click="store.setActiveSet(s.id)">
              {{ s.name }}
            </button>
            <button type="button" class="shrink-0 rounded p-1 text-ink-muted hover:text-ink-soft" title="重命名" @click="startRename(s)">
              <Icon name="edit" :size="13" />
            </button>
            <button
              type="button"
              class="shrink-0 rounded p-1 text-ink-muted hover:text-danger"
              title="删除"
              :disabled="store.userConfigSets.length <= 1"
              @click="store.deleteConfigSet(s.id)"
            >
              <Icon name="trash" :size="13" />
            </button>
          </div>
          <input
            v-if="renamingId === s.id"
            v-model="renameText"
            type="text"
            class="mb-1 w-full rounded-lg border border-brand/30 bg-white px-2 py-1 text-sm text-ink outline-none focus:ring-2 focus:ring-brand/10"
            @keyup.enter="commitRename(s)"
            @blur="commitRename(s)"
          />
        </div>
      </div>
    </aside>

    <!-- 右：选中配置套的六段编辑器 -->
    <div class="xb-scroll flex-1 min-h-0 overflow-auto">
      <div v-if="!store.activeSet" class="dash-card flex min-h-[300px] items-center justify-center text-ink-muted">请先在左侧创建配置套</div>
      <template v-else>
        <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 class="text-sm font-semibold text-ink">正在编辑：{{ store.activeSet.name }}</h3>
            <p class="text-xs text-ink-muted">配置套是一份完整模板；在「账号任务配置」里可指定某任务回填此套。</p>
          </div>
          <div class="flex items-center gap-2">
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
              :disabled="store.saving"
              @click="store.saveActiveSet"
            >
              <Icon name="check" :size="14" />{{ store.saving ? '保存中…' : '保存配置套' }}
            </button>
          </div>
        </div>

        <div class="rounded-xl border-l-4 border-brand/30 bg-brand/5 px-4 py-3 text-xs leading-relaxed text-ink-soft">
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
  </div>
</template>

<script setup>
import { ref } from 'vue'
import Icon from '@/components/Icon.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import TimeSection from '@/components/signconfig/sections/TimeSection.vue'
import LocationSection from '@/components/signconfig/sections/LocationSection.vue'
import RemarkSection from '@/components/signconfig/sections/RemarkSection.vue'
import ImageSection from '@/components/signconfig/sections/ImageSection.vue'
import PushSection from '@/components/signconfig/sections/PushSection.vue'
import AdvancedSection from '@/components/signconfig/sections/AdvancedSection.vue'
import MasonryGrid from '@/components/signconfig/MasonryGrid.vue'

const store = useSignConfigStore()

const renamingId = ref('')
const renameText = ref('')
function startRename(s) {
  renamingId.value = s.id
  renameText.value = s.name
}
function commitRename(s) {
  if (renamingId.value !== s.id) return
  const name = renameText.value.trim()
  if (name && name !== s.name) store.renameConfigSet(s.id, name)
  renamingId.value = ''
}
</script>
