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

    <!-- 弹性填充卡片：图库标签下随内容增高并设 90vh 最小高度（包住更高图库列表、页面整体滚动、背景不溢出，又不至于收得太窄）；
         其余资源池保持视口内滚动、同高留白，与全站卡片观感一致 -->
    <div
      class="dash-card fade-up flex flex-col p-4"
      :class="store.resourceSubTab === 'images' ? 'lg:min-h-[90vh]' : 'lg:flex-1 lg:min-h-0'"
    >
      <LocationPool v-if="store.resourceSubTab === 'locations'" :fixed-scope="isAdmin ? 'system' : 'user'" />
      <ImageLibrary v-else-if="store.resourceSubTab === 'images'" />
      <CredentialPool v-else-if="store.resourceSubTab === 'credentials'" />
      <UaTemplates v-else-if="store.resourceSubTab === 'ua'" />
    </div>

    <!-- 图库标签下卡片高于视口、会溢出父级 flex 盒，导致 SignConfigView 根级底部占位被覆盖、卡片贴浏览器底；
         此处补一个真实在流的占位块（仅图库标签），使滚动到底仍保留 24px 间距，与各页底部留白一致 -->
    <div
      v-if="store.resourceSubTab === 'images'"
      class="h-6 shrink-0 -mt-4"
      aria-hidden="true"
    ></div>
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
