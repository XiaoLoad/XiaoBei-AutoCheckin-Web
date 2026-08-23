<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-[1000] flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
      >
        <div class="absolute inset-0 bg-ink/50 backdrop-blur-[2px]" @click="onCancel" />

        <div
          class="modal-panel relative flex max-h-[92vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl shadow-ink/20"
          @click.stop
        >
          <!-- 标题 -->
          <div class="flex items-center justify-between px-5 pt-5">
            <h3 class="text-base font-semibold text-ink">
              {{ mode === 'edit' ? '编辑 B 平台账号' : '新增 B 平台账号' }}
            </h3>
            <button
              type="button"
              class="grid h-8 w-8 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud hover:text-ink"
              aria-label="关闭"
              @click="onCancel"
            >
              <Icon name="close" :size="18" />
            </button>
          </div>

          <form class="space-y-5 overflow-y-auto px-5 pb-2 pt-4" @submit.prevent="onSubmit">
            <!-- 账号信息 -->
            <div class="space-y-4">
              <div>
                <label class="mb-1.5 block text-sm font-medium text-ink-soft">B 平台账号</label>
                <input
                  v-model.trim="form.account"
                  type="text"
                  maxlength="64"
                  placeholder="如 A-301"
                  class="login-input"
                  :class="errors.account && 'border-danger focus:border-danger focus:ring-danger/10'"
                  @input="errors.account = ''"
                />
                <p v-if="errors.account" class="mt-1 text-xs text-danger">{{ errors.account }}</p>
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
                  @input="errors.password = ''"
                />
                <p v-if="errors.password" class="mt-1 text-xs text-danger">{{ errors.password }}</p>
              </div>

              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="mb-1.5 block text-sm font-medium text-ink-soft">签到类型</label>
                  <BaseSelect
                    v-model="form.type"
                    placeholder="签到类型"
                    :options="[
                      { label: '寝室', value: 'dorm' },
                      { label: '活动', value: 'activity' },
                      { label: '通用', value: 'general' }
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
                        class="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all"
                        :class="form.enabled ? 'left-[18px]' : 'left-0.5'"
                      />
                    </span>
                  </button>
                </div>
              </div>
            </div>

            <!-- 第三方账号校验 -->
            <div class="rounded-xl border border-ink/10 bg-cloud/40 p-4">
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <p class="text-sm font-medium text-ink-soft">账号密码校验</p>
                  <p class="mt-0.5 text-xs text-ink-muted">新增后对接 B 平台前，校验账号密码是否正确</p>
                </div>
                <button
                  type="button"
                  class="shrink-0 rounded-lg border border-brand/30 bg-brand/5 px-3 py-2 text-sm font-medium text-brand transition hover:bg-brand/10 disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="verifying || !form.account || !form.password"
                  @click="runVerify"
                >
                  <span v-if="verifying" class="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-brand/40 border-t-brand" />
                  <span v-else>校验账号</span>
                </button>
              </div>
              <p v-if="verifyState === 'ok'" class="mt-3 flex items-center gap-1.5 text-xs font-medium text-success">
                <Icon name="check-circle" :size="14" />{{ verifyMsg }}
              </p>
              <p v-else-if="verifyState === 'fail'" class="mt-3 flex items-center gap-1.5 text-xs font-medium text-danger">
                <Icon name="alert" :size="14" />{{ verifyMsg }}
              </p>
            </div>

            <!-- 个人信息（平台回填：用户不可手改，仅由 B 平台获取后写入） -->
            <div>
              <div class="mb-3 flex items-center gap-2">
                <span class="text-[11px] font-semibold tracking-wider text-ink-muted uppercase">个人信息</span>
                <span class="h-px flex-1 bg-ink/10" />
                <span class="inline-flex items-center gap-1 rounded-full bg-ink/5 px-2 py-0.5 text-xs text-ink-muted">
                  <Icon name="lock" :size="12" />仅平台回填
                </span>
                <button
                  type="button"
                  class="shrink-0 rounded-lg border border-brand/30 bg-brand/5 px-2.5 py-1 text-xs font-medium text-brand transition hover:bg-brand/10 disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="backfilling || !form.account"
                  @click="runBackfill"
                >
                  <span v-if="backfilling" class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-brand/40 border-t-brand" />
                  <span v-else>从平台回填</span>
                </button>
              </div>
              <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label class="mb-1.5 block text-sm font-medium text-ink-soft">姓名</label>
                  <input v-model.trim="form.profile.name" type="text" placeholder="从平台获取" disabled class="login-input bg-cloud/60 text-ink-muted cursor-not-allowed" />
                </div>
                <div>
                  <label class="mb-1.5 block text-sm font-medium text-ink-soft">学号</label>
                  <input v-model.trim="form.profile.studentNo" type="text" placeholder="从平台获取" disabled class="login-input bg-cloud/60 text-ink-muted cursor-not-allowed" />
                </div>
                <div>
                  <label class="mb-1.5 block text-sm font-medium text-ink-soft">学院</label>
                  <input v-model.trim="form.profile.college" type="text" placeholder="从平台获取" disabled class="login-input bg-cloud/60 text-ink-muted cursor-not-allowed" />
                </div>
                <div>
                  <label class="mb-1.5 block text-sm font-medium text-ink-soft">专业</label>
                  <input v-model.trim="form.profile.major" type="text" placeholder="从平台获取" disabled class="login-input bg-cloud/60 text-ink-muted cursor-not-allowed" />
                </div>
                <div class="sm:col-span-2">
                  <label class="mb-1.5 block text-sm font-medium text-ink-soft">班级</label>
                  <input v-model.trim="form.profile.className" type="text" placeholder="从平台获取" disabled class="login-input bg-cloud/60 text-ink-muted cursor-not-allowed" />
                </div>
              </div>
              <p class="mt-2 text-xs text-ink-muted">个人信息由 B 平台在登录后自动获取并回填，不可手动修改。</p>
            </div>

            <!-- 操作 -->
            <div class="sticky bottom-0 -mx-5 flex gap-3 border-t border-ink/5 bg-white px-5 py-4">
              <button
                type="button"
                class="flex-1 rounded-xl border border-ink/10 px-4 py-2.5 text-sm font-medium text-ink-soft transition hover:bg-cloud"
                @click="onCancel"
              >
                取消
              </button>
              <button
                type="submit"
                class="flex-1 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-70"
                :disabled="submitting"
              >
                {{ submitting ? '保存中…' : '保存' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import { fetchProfile } from '@/api/accounts'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  mode: { type: String, default: 'add' }, // add | edit
  account: { type: Object, default: null },
  submitting: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'submit', 'cancel'])

function emptyForm() {
  return {
    account: '',
    password: '',
    type: 'dorm',
    enabled: true,
    profile: { name: '', college: '', major: '', className: '', studentNo: '' }
  }
}

const form = reactive(emptyForm())
const errors = reactive({ account: '', password: '' })
const verifyState = ref('idle') // idle | checking | ok | fail
const verifying = ref(false)
const verifyMsg = ref('')
const backfilling = ref(false)

function resetForm() {
  Object.assign(form, emptyForm())
  errors.account = ''
  errors.password = ''
  verifyState.value = 'idle'
  verifyMsg.value = ''
  if (props.mode === 'edit' && props.account) {
    form.account = props.account.account || ''
    form.password = ''
    form.type = props.account.type || 'dorm'
    form.enabled = !!props.account.enabled
    form.profile = {
      name: '',
      college: '',
      major: '',
      className: '',
      studentNo: '',
      ...(props.account.profile || {})
    }
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) resetForm()
  },
  { immediate: true }
)

async function runVerify() {
  if (!form.account || !form.password) {
    verifyState.value = 'fail'
    verifyMsg.value = '请先填写账号与密码'
    return
  }
  verifying.value = true
  verifyState.value = 'checking'
  try {
    const res = await import('@/api/accounts').then((m) => m.verifyAccount(form.account, form.password))
    verifyState.value = res.ok ? 'ok' : 'fail'
    verifyMsg.value = res.message
  } catch (e) {
    verifyState.value = 'fail'
    verifyMsg.value = e.message || '校验失败'
  } finally {
    verifying.value = false
  }
}

// 从 B 平台获取个人信息并回填（平台写入，字段保持禁用）
async function runBackfill() {
  if (!form.account) return
  backfilling.value = true
  try {
    const profile = await fetchProfile(form.account)
    form.profile = { ...form.profile, ...profile }
  } finally {
    backfilling.value = false
  }
}

function validate() {
  errors.account = ''
  errors.password = ''
  let ok = true
  if (!form.account) {
    errors.account = '账号不能为空'
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
  return ok
}

async function onSubmit() {
  if (!validate()) return

  // 需要校验的场景：新增（必填密码）/ 编辑时修改了密码
  const needVerify = props.mode === 'add' || (props.mode === 'edit' && !!form.password)
  if (needVerify && verifyState.value !== 'ok') {
    await runVerify()
    if (verifyState.value !== 'ok') return
  }

  const payload = {
    account: form.account,
    type: form.type,
    enabled: form.enabled,
    profile: { ...form.profile }
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

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active .modal-panel,
.modal-leave-active .modal-panel {
  transition: transform 0.22s ease, opacity 0.22s ease;
}
.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  transform: translateY(8px) scale(0.98);
  opacity: 0;
}
</style>
