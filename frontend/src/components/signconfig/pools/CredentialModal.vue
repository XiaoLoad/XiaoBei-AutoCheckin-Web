<template>
  <BaseModal :model-value="open" :title="isEdit ? '编辑凭证' : '添加凭证'" @update:model-value="close">
    <p class="text-xs text-ink-muted">密钥以密文存储；编辑时未修改的密文字段会保留原值。</p>

    <div class="mt-4 space-y-3">
      <input
        v-model="form.name"
        class="w-full rounded-xl border border-ink/10 bg-elevated px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
        placeholder="凭证名称"
      />
      <div class="w-full">
        <BaseSelect v-model="form.type" :options="typeOptions" size="sm" :disabled="isEdit" placeholder="选择通道" />
      </div>

      <PushCredentialFields v-model="form.fields" :channel="form.type" />
    </div>

    <template #footer>
      <button type="button" class="h-9 rounded-lg px-4 text-sm font-medium text-ink-muted transition hover:bg-cloud" @click="close">取消</button>
      <button
        type="button"
        class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
        :disabled="!canSave || saving"
        @click="save"
      >
        <Icon v-if="saving" name="refresh" :size="14" class="animate-spin" />
        {{ saving ? '保存中' : '保存' }}
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import { reactive, computed, watch } from 'vue'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import BaseModal from '@/components/BaseModal.vue'
import PushCredentialFields from '@/components/PushCredentialFields.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { toast } from '@/utils/toast'

const props = defineProps({
  open: { type: Boolean, default: false },
  credential: { type: Object, default: null }
})
const emit = defineEmits(['close', 'saved'])

const store = useSignConfigStore()
const typeOptions = [
  { label: 'Server酱', value: 'serverchan' },
  { label: 'PushPlus', value: 'pushplus' },
  { label: 'PushPlus开放（群推送）', value: 'pushplus-open' },
  { label: '邮件', value: 'email' }
]
const isEdit = computed(() => !!props.credential)
const saving = computed(() => store.saving)

const blankFields = () => ({ serverchanKey: '', pushplusToken: '', token: '', emailSmtp: '', emailFrom: '', emailPass: '', emailTo: '' })
const form = reactive({ id: '', name: '', type: 'serverchan', fields: blankFields() })

// 打开时回填（新增=清空，编辑=载入凭证脱敏字段；密文占位由后端识别为「未修改」）
watch(
  () => [props.open, props.credential],
  () => {
    if (!props.open) return
    if (props.credential) {
      form.id = props.credential.id
      form.name = props.credential.name
      form.type = props.credential.type
      Object.assign(form.fields, blankFields(), props.credential.fields || {})
    } else {
      form.id = ''
      form.name = ''
      form.type = 'serverchan'
      Object.assign(form.fields, blankFields())
    }
  },
  { immediate: true }
)

const canSave = computed(() => !!form.name.trim())

async function save() {
  try {
    await store.saveCredential({
      id: form.id || undefined,
      name: form.name.trim(),
      type: form.type,
      fields: { ...form.fields }
    })
    toast(isEdit.value ? '凭证已更新' : '凭证已添加', 'success')
    emit('saved')
    close()
  } catch (e) {
    toast('保存失败，请检查必填项', 'error')
  }
}
function close() {
  emit('close')
}
</script>
