<template>
  <div class="flex flex-1 min-h-0 flex-col gap-6">
    <!-- 顶部：标题 + 一级 Tab 切换 -->
    <div class="dash-card fade-up shrink-0 p-3 sm:p-4">
      <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
        <div class="flex items-center gap-2">
          <span class="text-sm font-medium text-ink-soft">{{ title }}</span>
          <span class="hidden text-xs text-ink-muted sm:inline">{{ subtitle }}</span>
        </div>
        <div v-if="tabs.length > 1" class="ml-auto inline-flex items-center rounded-xl bg-cloud p-1">
          <button
            v-for="t in tabs"
            :key="t.value"
            type="button"
            class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition"
            :class="effectiveTab === t.value ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
            @click="store.setActiveTab(t.value)"
          >
            <Icon :name="t.icon" :size="15" />{{ t.label }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="store.loading" class="dash-card flex flex-1 items-center justify-center text-ink-muted">加载中…</div>
    <DefaultConfigTab v-else-if="effectiveTab === 'default'" />
    <AccountTaskConfigTab v-else-if="effectiveTab === 'tasks'" />
    <MyResourcesTab v-else-if="effectiveTab === 'resources'" />

    <div class="h-6 shrink-0 -mt-6" aria-hidden="true"></div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import Icon from '@/components/Icon.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { useAuthStore } from '@/store/modules/auth'
import DefaultConfigTab from '@/components/signconfig/DefaultConfigTab.vue'
import AccountTaskConfigTab from '@/components/signconfig/AccountTaskConfigTab.vue'
import MyResourcesTab from '@/components/signconfig/MyResourcesTab.vue'

const store = useSignConfigStore()
const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

// 角色分治：管理员管平台资源（仅系统位置池 + UA 模板）；普通用户用平台（配置套 + 账号任务 + 我的资源）
const tabs = computed(() =>
  isAdmin.value
    ? [{ value: 'resources', label: '系统资源', icon: 'layers' }]
    : [
        { value: 'default', label: '配置套', icon: 'sliders' },
        { value: 'tasks', label: '账号任务配置', icon: 'box' },
        { value: 'resources', label: '我的资源', icon: 'layers' }
      ]
)
// 标题按角色区分：管理员只维护平台级资源（位置池/UA 模板），不宜沿用「签到配置」
const title = computed(() => (isAdmin.value ? '平台资源' : '签到配置'))
const subtitle = computed(() =>
  isAdmin.value ? '平台级资源（位置池 · UA 模板），普通用户可选不可改' : '配置套 · 账号任务配置 · 我的资源'
)

// 兜底：切换角色后若 activeTab 不在当前角色 tabs 内，回落到第一个可用 Tab
const effectiveTab = computed(() => {
  const vals = tabs.value.map((t) => t.value)
  return vals.includes(store.activeTab) ? store.activeTab : tabs.value[0]?.value || 'default'
})

onMounted(() => {
  store.load()
})
</script>
