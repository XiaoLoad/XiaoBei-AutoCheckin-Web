<template>
  <div class="space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="text-xs text-ink-muted">各推送通道的密钥集中保管（Fernet 加密落库），配置推送时直接回填，无需重复填写。</p>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white shadow-lg shadow-brand/20 transition hover:bg-brand-dark"
        @click="openAdd"
      >
        <Icon name="plus" :size="15" />添加凭证
      </button>
    </div>

    <div v-if="store.credentials.length === 0" class="flex flex-col items-center gap-2 py-10 text-ink-muted">
      <Icon name="send" :size="30" class="opacity-40" />
      <p class="text-sm">暂无凭证</p>
      <p class="text-xs">添加 Server酱 / PushPlus / 邮箱凭证后，可在配置套中开启签到结果推送</p>
    </div>

    <TransitionGroup v-else tag="div" class="grid grid-cols-1 gap-2.5 sm:grid-cols-2" name="cred-list">
      <article
        v-for="c in store.credentials"
        :key="c.id"
        class="cred-card group relative overflow-hidden rounded-xl border border-ink/10 bg-white p-3.5 transition duration-300 hover:-translate-y-0.5 hover:border-brand/30 hover:shadow-md hover:shadow-ink/5"
      >
        <div class="flex items-start gap-3">
          <!-- 通道徽标：品牌化底色 + 通道缩写 -->
          <span
            class="grid h-10 w-10 shrink-0 place-items-center rounded-lg text-xs font-bold"
            :class="channelCls(c.type)"
          >{{ channelShort(c.type) }}</span>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-1.5">
              <p class="min-w-0 flex-1 truncate text-sm font-semibold text-ink" :title="c.name">{{ c.name }}</p>
              <span
                class="shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium"
                :class="c.enabled ? 'bg-success/10 text-success' : 'bg-ink/10 text-ink-muted'"
              >{{ c.enabled ? '启用' : '停用' }}</span>
            </div>
            <p class="mt-0.5 text-xs text-ink-muted">{{ typeLabel(c.type) }} · 密文保管，仅推送时解密使用</p>
          </div>
        </div>

        <!-- 操作行 -->
        <div class="mt-3 flex items-center justify-between gap-2 border-t border-ink/5 pt-2.5">
          <button
            type="button"
            class="inline-flex h-7 items-center gap-1.5 rounded-lg border border-brand/30 bg-brand/5 px-2.5 text-xs font-medium text-brand transition hover:bg-brand/10 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="testing === c.id"
            @click="testPush(c)"
          >
            <span v-if="testing === c.id" class="inline-flex items-center gap-1">
              <Icon name="refresh" :size="12" class="animate-spin" />测试中…
            </span>
            <span v-else class="inline-flex items-center gap-1">
              <Icon name="send" :size="12" />测试推送
            </span>
          </button>
          <div class="flex items-center gap-1">
            <button
              type="button"
              class="grid h-7 w-7 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud hover:text-brand"
              title="编辑"
              @click="openEdit(c)"
            >
              <Icon name="edit" :size="13" />
            </button>
            <button
              v-if="confirmingId !== c.id"
              type="button"
              class="grid h-7 w-7 place-items-center rounded-lg text-ink-muted transition hover:bg-danger/10 hover:text-danger"
              title="删除"
              @click="confirmingId = c.id"
            >
              <Icon name="trash" :size="13" />
            </button>
            <template v-else>
              <button type="button" class="rounded-lg px-2 py-1 text-[11px] font-medium text-ink-muted transition hover:bg-cloud" @click="confirmingId = null">取消</button>
              <button
                type="button"
                class="rounded-lg bg-danger px-2 py-1 text-[11px] font-medium text-white transition hover:bg-danger/90"
                @click="confirmDel(c)"
              >确认删除</button>
            </template>
          </div>
        </div>
      </article>
    </TransitionGroup>

    <CredentialModal :open="modalOpen" :credential="editing" @close="modalOpen = false" @saved="onSaved" />
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'
import CredentialModal from './CredentialModal.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { toast } from '@/utils/toast'

const store = useSignConfigStore()
const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const typeOptions = [
  { label: 'Server酱', value: 'serverchan' },
  { label: 'PushPlus', value: 'pushplus' },
  { label: '邮件', value: 'email' }
]
const modalOpen = ref(false)
const editing = ref(null)
const testing = ref(null) // 正在测试的凭证 id
const confirmingId = ref(null) // 两步删除确认

function typeLabel(t) {
  return (typeOptions.find((o) => o.value === t) || {}).label || t
}
function channelCls(t) {
  return { serverchan: 'bg-brand/10 text-brand', pushplus: 'bg-success/10 text-success', email: 'bg-info/10 text-info' }[t] || 'bg-ink/10 text-ink-soft'
}
function channelShort(t) {
  return { serverchan: 'SC', pushplus: 'PP', email: '@' }[t] || '··'
}
function openAdd() {
  editing.value = null
  modalOpen.value = true
}
function openEdit(c) {
  editing.value = c
  modalOpen.value = true
}
function onSaved() {
  // store 已刷新 credentials，无需额外处理
}
function confirmDel(c) {
  confirmingId.value = null
  store.deleteCredential(c.id)
}
async function testPush(c) {
  testing.value = c.id
  try {
    await store.testPushCredential(c.id, 'html')
    toast('测试推送已发送，请查收', 'success')
  } catch (e) {
    toast('测试推送失败，请检查凭证或通道配置', 'error')
  } finally {
    testing.value = null
  }
}

// 卡片错峰入场（增删后重放；尊重减少动效偏好）
watch(() => store.credentials.length, async () => {
  if (prefersReduced) return
  await nextTick()
  gsap.fromTo(
    '.cred-card',
    { opacity: 0, y: 10 },
    { opacity: 1, y: 0, duration: 0.35, stagger: 0.06, ease: 'power2.out', clearProps: 'opacity,transform' }
  )
})
</script>
