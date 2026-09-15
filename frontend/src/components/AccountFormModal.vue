<template>
  <!-- 新增/编辑 B 平台账号弹窗：基于 BaseModal 组装（遮罩/ESC/滚动锁定/过渡均由骨架提供）。
       表单只包字段区（回车触发 submit），底部按钮在 footer 插槽经 click 提交。 -->
  <BaseModal
    :model-value="modelValue"
    size="xl"
    :title="mode === 'edit' ? '编辑 B 平台账号' : '新增 B 平台账号'"
    @update:model-value="(v) => emit('update:modelValue', v)"
    @cancel="onCancel"
  >
    <form class="space-y-5" @submit.prevent="onSubmit">
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

            <!-- 推送凭证：账号级归属。凭证属于账号本身，配置套只决定"用不用它" -->
            <div>
              <div class="mb-3 flex items-center gap-2">
                <span class="text-[11px] font-semibold tracking-wider text-ink-muted uppercase">推送凭证</span>
                <span class="h-px flex-1 bg-ink/10" />
                <span class="inline-flex items-center gap-1 rounded-full bg-ink/5 px-2 py-0.5 text-xs text-ink-muted">
                  已绑定 {{ boundCount }} / {{ PUSH_CHANNELS.length }}
                </span>
              </div>

              <p class="mb-3 text-xs text-ink-muted">
                绑定后这个账号的签到结果推送到它自己的凭证，一个配置套套用多个账号时互不串号；留空则跟随配置套里的凭证。
              </p>

              <div class="space-y-3">
                <div v-for="ch in PUSH_CHANNELS" :key="ch" class="space-y-2">
                  <div class="flex items-center gap-2.5">
                    <span class="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-[10px] font-bold" :class="channelTone(ch)">
                      {{ channelShort(ch) }}
                    </span>
                    <span class="w-16 shrink-0 text-sm text-ink-soft">{{ channelLabel(ch) }}</span>
                    <!-- 归属连线：已落位为实线、未落位为虚线，一眼看出哪些通道还没配 -->
                    <span
                      class="min-w-[1rem] flex-1"
                      :class="entryFilled(ch) ? 'h-px bg-brand/30' : 'border-t border-dashed border-ink/20'"
                    />
                    <BaseSelect
                      v-if="credOptionsOf(ch).length > 1"
                      :model-value="form.pushCreds[ch].credId"
                      :options="credOptionsOf(ch)"
                      placement="auto"
                      placeholder="跟随配置套"
                      size="sm"
                      class="w-40 shrink-0 sm:w-56"
                      @update:model-value="(v) => (form.pushCreds[ch].credId = v)"
                    />
                    <button
                      v-else
                      type="button"
                      class="inline-flex w-40 shrink-0 items-center justify-center gap-1 rounded-xl border border-dashed border-brand/40 bg-brand/5 px-3 py-1.5 text-xs font-medium text-brand transition hover:bg-brand/10 sm:w-56"
                      @click="openInlineNew(ch)"
                    >
                      <Icon name="plus" :size="13" />新建凭证
                    </button>
                  </div>

                  <!-- 邮件收件人：与凭证选择正交，不绑凭证也能单独指定发给谁 -->
                  <div v-if="ch === 'email'" class="flex items-start gap-2.5 pl-[7rem]">
                    <span class="w-16 shrink-0 pt-2 text-xs text-ink-muted">收件人</span>
                    <div class="min-w-0 flex-1">
                      <input
                        v-model.trim="form.pushCreds.email.to"
                        type="text"
                        autocomplete="off"
                        class="w-full rounded-xl border border-ink/10 bg-white px-3 py-1.5 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
                        placeholder="多个用逗号分隔"
                      />
                      <p class="mt-1 text-xs text-ink-muted">{{ recipientHint }}</p>
                    </div>
                  </div>

                  <!-- 就地新建凭证：省掉「先去我的资源建好再回来下拉」这一趟，也不丢已填内容 -->
                  <div v-if="inlineNew && inlineNew.channel === ch" class="pl-[7rem]">
                    <div class="rounded-xl border border-dashed border-ink/15 bg-cloud/40 p-3">
                      <div class="flex items-center justify-between gap-2">
                        <p class="text-xs font-medium text-ink-soft">新建 {{ channelLabel(ch) }} 凭证</p>
                        <button type="button" class="text-xs text-ink-muted transition hover:text-ink" @click="inlineNew = null">取消</button>
                      </div>
                      <div class="mt-2.5 space-y-3">
                        <div>
                          <label class="mb-1.5 block text-xs text-ink-muted">凭证名称</label>
                          <input
                            v-model.trim="inlineNew.name"
                            type="text"
                            autocomplete="off"
                            maxlength="64"
                            class="w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
                            placeholder="如 我的 QQ 邮箱"
                          />
                        </div>
                        <PushCredentialFields v-model="inlineNew.fields" :channel="ch" />
                      </div>
                      <div class="mt-3 flex justify-end">
                        <button
                          type="button"
                          class="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-xs font-medium text-white shadow-lg shadow-brand/20 transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-60"
                          :disabled="!inlineNew.name || creatingCred"
                          @click="saveInlineCredential(ch)"
                        >
                          <span v-if="creatingCred" class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                          {{ creatingCred ? '保存中…' : '保存并绑定' }}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <p class="mt-3 text-xs text-ink-muted">
                凭证在「我的资源 · 我的凭证」统一维护，密文保管、可随时测试推送。
              </p>
            </div>

            <!-- 个人信息（平台回填：用户不可手改，仅由 B 平台获取后写入） -->
            <div>
              <div class="mb-3 flex items-center gap-2">
                <span class="text-[11px] font-semibold tracking-wider text-ink-muted uppercase">个人信息</span>
                <span class="h-px flex-1 bg-ink/10" />
                <span class="inline-flex items-center gap-1 rounded-full bg-ink/5 px-2 py-0.5 text-xs text-ink-muted">
                  <Icon name="lock" :size="12" />校验通过自动回填
                </span>
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
              <p class="mt-2 text-xs text-ink-muted">账号密码校验通过后，个人信息由 B 平台自动获取并回填，无需手动操作。</p>
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
import { computed, reactive, ref, watch } from 'vue'
import BaseModal from '@/components/BaseModal.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import Icon from '@/components/Icon.vue'
import PushCredentialFields from '@/components/PushCredentialFields.vue'
import { fetchProfile } from '@/api/accounts'
import { fetchCredentials, createCredential } from '@/api/signConfig'
import {
  PUSH_CHANNELS,
  channelLabel,
  channelShort,
  channelTone,
  normalizePushCreds,
  serializePushCreds
} from '@/utils/pushChannels'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  mode: { type: String, default: 'add' }, // add | edit
  account: { type: Object, default: null },
  submitting: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'submit', 'cancel'])

// 凭证池里可选的推送凭证（按通道分组），随弹窗打开时拉取
const credentials = ref([])
const creatingCred = ref(false)
// 就地新建凭证的草稿：{ channel, name, fields }，同一时刻只开一个
const inlineNew = ref(null)

function blankFields() {
  return {
    serverchanKey: '', pushplusToken: '',
    emailSmtp: '', emailFrom: '', emailPass: '', emailTo: ''
  }
}

function emptyForm() {
  return {
    account: '',
    password: '',
    enabled: true,
    profile: { name: '', college: '', major: '', className: '', studentNo: '' },
    pushCreds: normalizePushCreds(null)
  }
}

const form = reactive(emptyForm())
const errors = reactive({ account: '', password: '' })
const verifyState = ref('idle') // idle | checking | ok | fail
const verifying = ref(false)
const verifyMsg = ref('')

const boundCount = computed(() => PUSH_CHANNELS.filter((ch) => !!form.pushCreds[ch].credId).length)

// 已选邮箱凭证的默认收件人：作为留空时的回落说明，写进提示而不是输入框占位
const recipientHint = computed(() => {
  const cid = form.pushCreds.email.credId
  const hit = credentials.value.find((c) => c.id === cid)
  const fallback = (hit && hit.fields && hit.fields.emailTo) || ''
  return fallback
    ? `留空则用凭证的默认收件人（${fallback}）`
    : '留空则用凭证的默认收件人；凭证没写默认值时，这里必须填'
})

// 该通道是否已有落位内容（绑了凭证或单独指定了收件人）——决定归属连线实线/虚线
function entryFilled(ch) {
  const e = form.pushCreds[ch]
  return !!(e.credId || e.to)
}

// 每行通道的选项：首项「跟随配置套」用于解绑，其余为该通道下的凭证
function credOptionsOf(ch) {
  const mine = credentials.value
    .filter((c) => c.type === ch)
    .map((c) => ({ label: c.name, value: c.id }))
  return [{ label: '跟随配置套', value: null }, ...mine]
}

async function loadCredentials() {
  try {
    credentials.value = await fetchCredentials()
  } catch {
    credentials.value = [] // 拉取失败只影响可选项，不阻断账号表单（错误已由全局提示）
  }
}

function openInlineNew(ch) {
  inlineNew.value = { channel: ch, name: '', fields: blankFields() }
}

async function saveInlineCredential(ch) {
  const draft = inlineNew.value
  if (!draft || !draft.name) return
  creatingCred.value = true
  try {
    const created = await createCredential({ name: draft.name, type: ch, fields: { ...draft.fields } })
    // 接口返回单条，补上列表用的 type 别名后并进本地选项，避免为一条新凭证重拉整个池
    credentials.value = [...credentials.value, { ...created, type: created.channel }]
    form.pushCreds[ch].credId = created.id
    inlineNew.value = null
  } catch {
    // 失败原因（缺必填项 / 格式错）已由请求层统一 toast；保留草稿让用户改完重试
  } finally {
    creatingCred.value = false
  }
}

function resetForm() {
  Object.assign(form, emptyForm())
  errors.account = ''
  errors.password = ''
  verifyState.value = 'idle'
  verifyMsg.value = ''
  inlineNew.value = null
  if (props.mode === 'edit' && props.account) {
    form.account = props.account.account || ''
    form.password = ''
    form.enabled = !!props.account.enabled
    form.profile = {
      name: '',
      college: '',
      major: '',
      className: '',
      studentNo: '',
      ...(props.account.profile || {})
    }
    form.pushCreds = normalizePushCreds(props.account.pushCreds)
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      resetForm()
      loadCredentials()
    }
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
    if (res.ok) await backfillProfile() // 校验通过即自动回填，无需用户手动触发
  } catch (e) {
    verifyState.value = 'fail'
    verifyMsg.value = e.message || '校验失败'
  } finally {
    verifying.value = false
  }
}

// 校验成功后从 B 平台档案自动回填（预检已缓存 profile，此处即时返回；字段保持禁用）
async function backfillProfile() {
  if (!form.account) return
  const profile = await fetchProfile(form.account)
  form.profile = { ...form.profile, ...profile }
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
    enabled: form.enabled,
    profile: { ...form.profile },
    // 只落有内容的项；空对象即"清空绑定"，后端据此把 push_cred_json 置 NULL
    pushCreds: serializePushCreds(form.pushCreds)
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
