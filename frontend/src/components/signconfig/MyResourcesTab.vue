<template>
  <!-- flex-1 min-h-0：填满签到配置页内容区，使图库等子页可内部滚动而非把卡片撑出视口 -->
  <div class="flex flex-col gap-4 lg:min-h-0 lg:flex-1">
    <div class="inline-flex shrink-0 rounded-xl bg-cloud p-1 text-sm">
      <button
        v-for="t in tabs"
        :key="t.value"
        type="button"
        class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-medium transition"
        :class="store.resourceSubTab === t.value ? 'bg-elevated text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
        @click="store.setResourceSubTab(t.value)"
      >
        <Icon :name="t.icon" :size="15" />{{ t.label }}
      </button>
    </div>

    <!-- 弹性填充卡片：图库需要视口内滚动（避免底部贴边）；其余资源池列表少时卡片同高留白，与全站卡片观感一致 -->
    <div class="dash-card fade-up flex flex-col p-4 lg:min-h-0 lg:flex-1">
      <LocationPool v-if="store.resourceSubTab === 'locations'" :fixed-scope="isAdmin ? 'system' : 'user'" />
      <ImageLibrary v-else-if="store.resourceSubTab === 'images'" />
      <CredentialPool v-else-if="store.resourceSubTab === 'credentials'" />
      <UaTemplates v-else-if="store.resourceSubTab === 'ua'" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Icon from '@/components/Icon.vue'
import { useAuthStore } from '@/stores/auth'
import { useSignConfigStore } from '@/stores/signConfig'
import LocationPool from '@/components/signconfig/pools/LocationPool.vue'
import ImageLibrary from '@/components/signconfig/pools/ImageLibrary.vue'
import CredentialPool from '@/components/signconfig/pools/CredentialPool.vue'
import UaTemplates from '@/components/signconfig/pools/UaTemplates.vue'

const auth = useAuthStore()
const store = useSignConfigStore()
const isAdmin = computed(() => auth.isAdmin)

// 角色分治：管理员维护平台级资源（位置池 + UA 模板）；普通用户维护自己的资源（位置池 + 图库 + 凭证）
const tabs = computed(() =>
  isAdmin.value
    ? [
        { value: 'locations', label: '位置池', icon: 'map-pin' },
        { value: 'ua', label: 'UA 模板', icon: 'settings' }
      ]
    : [
        { value: 'locations', label: '位置池', icon: 'map-pin' },
        { value: 'images', label: '图库', icon: 'image' },
        { value: 'credentials', label: '凭证', icon: 'send' }
      ]
)
</script>
