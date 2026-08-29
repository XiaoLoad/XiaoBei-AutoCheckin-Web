<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between">
      <p class="text-xs text-ink-muted">我的凭证：各推送通道的密钥集中保管，配置推送时可直接回填，无需重复填写。</p>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-dark"
        @click="openAdd"
      >
        <Icon name="plus" :size="15" />添加凭证
      </button>
    </div>

    <div v-if="store.credentials.length === 0" class="py-8 text-center text-sm text-ink-muted">暂无凭证</div>
    <div v-else class="space-y-2">
      <div
        v-for="c in store.credentials"
        :key="c.id"
        class="flex items-center justify-between rounded-xl border border-ink/10 bg-white px-3 py-2"
      >
        <div class="min-w-0">
          <p class="text-sm font-medium text-ink">{{ c.name }}</p>
          <p class="text-xs text-ink-muted">类型：{{ typeLabel(c.type) }}</p>
        </div>
        <div class="flex shrink-0 items-center gap-3">
          <button
            type="button"
            class="text-xs text-brand hover:underline disabled:opacity-50"
            :disabled="testing === c.id"
            @click="testPush(c)"
          >
            <span v-if="testing === c.id" class="inline-flex items-center gap-1">
              <Icon name="refresh" :size="12" class="animate-spin" />测试中
            </span>
            <span v-else>测试推送</span>
          </button>
          <button type="button" class="text-xs text-brand hover:underline" @click="openEdit(c)">编辑</button>
          <button type="button" class="text-xs text-danger hover:underline" @click="store.deleteCredential(c.id)">删除</button>
        </div>
      </div>
    </div>

    <CredentialModal :open="modalOpen" :credential="editing" @close="modalOpen = false" @saved="onSaved" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import Icon from '@/components/Icon.vue'
import CredentialModal from './CredentialModal.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { toast } from '@/utils/toast'

const store = useSignConfigStore()
const typeOptions = [
  { label: 'Server酱', value: 'serverchan' },
  { label: 'PushPlus', value: 'pushplus' },
  { label: '邮件', value: 'email' }
]
const modalOpen = ref(false)
const editing = ref(null)
const testing = ref(null) // 正在测试的凭证 id

function typeLabel(t) {
  return (typeOptions.find((o) => o.value === t) || {}).label || t
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
</script>
