<template>
  <!-- 新增/编辑用户弹窗：基于 BaseModal 组装（遮罩/ESC/滚动锁定/过渡均由骨架提供）。
       表单只包字段区（回车触发 submit），底部按钮在 footer 插槽经 click 提交。 -->
  <BaseModal
    :model-value="modelValue"
    size="md"
    :title="mode === 'edit' ? '编辑用户' : '新增用户'"
    @update:model-value="(v) => emit('update:modelValue', v)"
    @cancel="onCancel"
  >
    <form class="space-y-4" @submit.prevent="onSubmit">
      <div>
        <label class="mb-1.5 block text-sm font-medium text-ink-soft">用户名</label>
        <input
          v-model.trim="form.username"
          type="text"
          maxlength="64"
          placeholder="仅字母、数字、下划线、连字符、点"
          class="login-input"
          :class="errors.username && 'border-danger focus:border-danger focus:ring-danger/10'"
          @input="onUsernameInput"
        />
        <p v-if="errors.username" class="mt-1 text-xs text-danger">{{ errors.username }}</p>
      </div>

      <div>
        <label class="mb-1.5 block text-sm font-medium text-ink-soft">
          备注
          <span class="font-normal text-ink-muted">（可选，如真实姓名、寝室号）</span>
        </label>
        <input
          v-model.trim="form.remark"
          type="text"
          maxlength="128"
          placeholder="便于区分用户，可留空"
          class="login-input"
          :class="errors.remark && 'border-danger focus:border-danger focus:ring-danger/10'"
          @input="errors.remark = ''"
        />
        <p v-if="errors.remark" class="mt-1 text-xs text-danger">{{ errors.remark }}</p>
      </div>

      <div>
        <label class="mb-1.5 block text-sm font-medium text-ink-soft">
          密码
          <span class="font-normal text-ink-muted">{{ mode === 'edit' ? '（留空则不修改）' : '' }}</span>
        </label>
        <input
          v-model="form.password"
          type="password"
          maxlength="64"
          placeholder="至少 6 位"
          class="login-input"
          :class="errors.password && 'border-danger focus:border-danger focus:ring-danger/10'"
          @input="onPasswordInput"
        />
        <p v-if="errors.password" class="mt-1 text-xs text-danger">{{ errors.password }}</p>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">角色</label>
          <BaseSelect
            v-model="form.role"
            placeholder="角色"
            :options="[
              { label: '普通用户', value: 'user' },
              { label: '管理员', value: 'admin' }
            ]"
          />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">状态</label>
          <button
            type="button"
            class="flex h-[46px] w-full items-center justify-between rounded-xl border border-ink/10 bg-cloud/60 px-4 text-sm transition"
            :class="form.enabled ? 'text-success' : 'text-ink-muted'"
            @click="form.enabled = !form.enabled"
          >
            <span>{{ form.enabled ? '启用' : '禁用' }}</span>
            <span
              class="relative h-5 w-9 rounded-full transition"
              :class="form.enabled ? 'bg-success' : 'bg-ink/25'"
            >
              <span
                class="absolute top-0.5 h-4 w-4 rounded-full bg-elevated shadow transition-all"
                :class="form.enabled ? 'left-[18px]' : 'left-0.5'"
              />
            </span>
          </button>
        </div>
      </div>

      <div>
        <label class="mb-1.5 block text-sm font-medium text-ink-soft">额度（总次数）</label>
        <input
          v-model.number="form.quota"
          type="number"
          min="0"
          class="login-input"
          :class="errors.quota && 'border-danger focus:border-danger focus:ring-danger/10'"
          @input="errors.quota = ''"
        />
        <p v-if="errors.quota" class="mt-1 text-xs text-danger">{{ errors.quota }}</p>
      </div>
    </form>

    <template #footer>
      <button
        type="button"
        class="flex-1 rounded-xl border border-ink/10 px-4 py-2.5 text-sm font-medium text-ink-soft transition hover:bg-cloud"
        @click="onCancel"
      >
        取消
      </button>
      <button
        type="button"
        class="flex-1 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-70"
        :disabled="submitting"
        @click="onSubmit"
      >
        {{ submitting ? '保存中…' : '保存' }}
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import { reactive, watch } from 'vue'
import BaseModal from '@/components/BaseModal.vue'
import BaseSelect from '@/components/BaseSelect.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  mode: { type: String, default: 'add' }, // add | edit
  user: { type: Object, default: null },
  submitting: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'submit', 'cancel'])

const form = reactive({ username: '', remark: '', password: '', role: 'user', enabled: true, quota: 100 })
const errors = reactive({ username: '', remark: '', password: '', quota: '' })

// 账号/密码特殊字符规则：
// 用户名仅允许 字母/数字/下划线/连字符/点；密码禁止控制字符与 HTML/SQL 危险元字符，
// 其余可见字符放行以保证口令强度。输入即过滤（限制非法字符），提交再校验提示。
const USERNAME_RE = /^[A-Za-z0-9_.\-]+$/
function sanitizeUsername(v) {
  return (v || '').split('').filter((ch) => USERNAME_RE.test(ch)).join('')
}
function sanitizePassword(v) {
  return (v || '')
    .split('')
    .filter((ch) => {
      const code = ch.charCodeAt(0)
      if (code < 32) return false // 控制字符
      if ('<>"\'`;\\|'.includes(ch)) return false // 危险元字符
      return true
    })
    .join('')
}

function onUsernameInput() {
  const cleaned = sanitizeUsername(form.username)
  if (cleaned !== form.username) form.username = cleaned
  errors.username = ''
}
function onPasswordInput() {
  const cleaned = sanitizePassword(form.password)
  if (cleaned !== form.password) form.password = cleaned
  errors.password = ''
}

function resetForm() {
  errors.username = ''
  errors.remark = ''
  errors.password = ''
  errors.quota = ''
  if (props.mode === 'edit' && props.user) {
    form.username = props.user.username || ''
    form.remark = props.user.remark || ''
    form.password = ''
    form.role = props.user.role || 'user'
    form.enabled = !!props.user.enabled
    form.quota = props.user.quota ?? 100
  } else {
    form.username = ''
    form.remark = ''
    form.password = ''
    form.role = 'user'
    form.enabled = true
    form.quota = 100
  }
}

// 每次打开时根据 mode/user 重置表单
watch(
  () => props.modelValue,
  (open) => {
    if (open) resetForm()
  },
  { immediate: true }
)

function validate() {
  errors.username = ''
  errors.remark = ''
  errors.password = ''
  errors.quota = ''
  let ok = true
  // 兜底再过滤一次（理论上输入时已处理），确保提交数据无非法字符
  form.username = sanitizeUsername(form.username)
  form.password = sanitizePassword(form.password)
  if (!form.username) {
    errors.username = '用户名不能为空'
    ok = false
  } else if (!USERNAME_RE.test(form.username)) {
    errors.username = '用户名仅支持字母、数字、下划线、连字符、点'
    ok = false
  }
  if ((form.remark || '').length > 128) {
    errors.remark = '备注最长 128 字符'
    ok = false
  }
  if (props.mode === 'add' && (!form.password || form.password.length < 6)) {
    errors.password = '密码至少 6 位'
    ok = false
  }
  if (props.mode === 'edit' && form.password && form.password.length < 6) {
    errors.password = '密码至少 6 位'
    ok = false
  }
  if (form.quota === '' || form.quota === null || Number.isNaN(Number(form.quota)) || Number(form.quota) < 0) {
    errors.quota = '额度需为不小于 0 的整数'
    ok = false
  }
  return ok
}

function onSubmit() {
  if (!validate()) return
  const payload = {
    username: form.username,
    remark: form.remark || '',
    role: form.role,
    enabled: form.enabled,
    quota: Number(form.quota)
  }
  if (form.password) payload.password = form.password
  emit('submit', payload)
}

function close() {
  emit('update:modelValue', false)
}

function onCancel() {
  emit('cancel')
  close()
}

defineExpose({ close })
</script>
