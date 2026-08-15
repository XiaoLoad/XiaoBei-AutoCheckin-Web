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

    <div v-if="editing" class="rounded-xl border border-brand/20 bg-brand/5 p-3">
      <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <input v-model="form.name" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="凭证名称" />
        <BaseSelect v-model="form.type" :options="typeOptions" size="sm" />
        <input v-if="form.type === 'serverchan'" v-model="form.fields.serverchanKey" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10 sm:col-span-2" placeholder="Server酱 SendKey" />
        <input v-if="form.type === 'pushplus'" v-model="form.fields.pushplusToken" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10 sm:col-span-2" placeholder="PushPlus Token" />
        <template v-if="form.type === 'email'">
          <input v-model="form.fields.emailSmtp" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="SMTP 地址" />
          <input v-model="form.fields.emailFrom" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="发件人" />
          <input v-model="form.fields.emailPass" type="password" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="授权码" />
          <input v-model="form.fields.emailTo" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="收件人" />
        </template>
      </div>
      <div class="mt-2 flex justify-end gap-2">
        <button class="rounded-lg border border-ink/10 px-3 py-1.5 text-sm text-ink-soft hover:bg-cloud" @click="editing = null">取消</button>
        <button class="rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark" :disabled="!form.name" @click="save">保存</button>
      </div>
    </div>

    <div v-if="store.credentials.length === 0" class="py-8 text-center text-sm text-ink-muted">暂无凭证</div>
    <div v-else class="space-y-2">
      <div v-for="c in store.credentials" :key="c.id" class="flex items-center justify-between rounded-xl border border-ink/10 bg-white px-3 py-2">
        <div>
          <p class="text-sm font-medium text-ink">{{ c.name }}</p>
          <p class="text-xs text-ink-muted">类型：{{ typeLabel(c.type) }}</p>
        </div>
        <div class="flex gap-3">
          <button class="text-xs text-brand hover:underline" @click="openEdit(c)">编辑</button>
          <button class="text-xs text-danger hover:underline" @click="store.deleteCredential(c.id)">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import { useSignConfigStore } from '@/stores/signConfig'

const store = useSignConfigStore()
const typeOptions = [
  { label: 'Server酱', value: 'serverchan' },
  { label: 'PushPlus', value: 'pushplus' },
  { label: '邮件', value: 'email' }
]
const editing = ref(false)
const form = reactive({ id: '', name: '', type: 'serverchan', fields: { serverchanKey: '', pushplusToken: '', emailSmtp: '', emailFrom: '', emailPass: '', emailTo: '' } })

function typeLabel(t) {
  return (typeOptions.find((o) => o.value === t) || {}).label || t
}
function openAdd() {
  form.id = ''
  form.name = ''
  form.type = 'serverchan'
  Object.assign(form.fields, { serverchanKey: '', pushplusToken: '', emailSmtp: '', emailFrom: '', emailPass: '', emailTo: '' })
  editing.value = true
}
function openEdit(c) {
  form.id = c.id
  form.name = c.name
  form.type = c.type
  Object.assign(form.fields, c.fields)
  editing.value = true
}
async function save() {
  await store.saveCredential({ id: form.id || undefined, name: form.name, type: form.type, fields: { ...form.fields } })
  editing.value = false
}
</script>
