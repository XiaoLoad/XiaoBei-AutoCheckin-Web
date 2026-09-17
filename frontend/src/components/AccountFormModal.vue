<template>
  <!-- 新增/编辑 B 平台账号弹窗：基于 BaseModal 组装（遮罩/ESC/滚动锁定/过渡均由骨架提供）。
       表单只包字段区（回车触发 submit），底部按钮在 footer 插槽经 click 提交。
       版面：身份与校验 → 推送去向 → 平台档案。可写内容一律带边框控件、只读读数一律内嵌
       cloud 块，沿用全站「形状即语义」的规则，不靠标题区分层级。 -->
  <BaseModal
    :model-value="modelValue"
    size="xl"
    :title="mode === 'edit' ? '编辑 B 平台账号' : '新增 B 平台账号'"
    @update:model-value="(v) => emit('update:modelValue', v)"
    @cancel="onCancel"
  >
    <form class="space-y-6" @submit.prevent="onSubmit">
      <!-- 身份与校验：账号/密码为两列字段，其下是两个动作（启用开关与校验），
           两者几何一致、并排成一行，末尾承载校验结论 -->
      <section class="space-y-4">
        <div class="grid gap-4 sm:grid-cols-2">
          <div>
            <label class="mb-1.5 block text-sm font-medium text-ink-soft" for="acc-account">B 平台账号</label>
            <input
              id="acc-account"
              v-model.trim="form.account"
              type="text"
              maxlength="64"
              placeholder="如 A-301"
              class="login-input"
              :class="errors.account && 'border-danger focus:border-danger focus:ring-danger/10'"
              @input="onCredentialInput('account')"
            />
            <p v-if="errors.account" class="mt-1 text-xs text-danger">{{ errors.account }}</p>
          </div>

          <div>
            <label class="mb-1.5 block text-sm font-medium text-ink-soft" for="acc-password">
              密码
              <span v-if="mode === 'edit'" class="font-normal text-ink-muted">（留空不修改）</span>
            </label>
            <!-- 显示开关由组件自持：浏览器原生的「小眼睛」只在首次输入时出现，
                 编辑态密码框本来就是空的，那里没有它，所以这里始终提供 -->
            <div class="relative">
              <input
                id="acc-password"
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                maxlength="64"
                placeholder="至少 6 位"
                class="login-input pwd-input pr-11"
                :class="errors.password && 'border-danger focus:border-danger focus:ring-danger/10'"
                @input="onCredentialInput('password')"
              />
              <button
                type="button"
                class="absolute right-2.5 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud hover:text-brand"
                :aria-label="showPassword ? '隐藏密码' : '显示密码'"
                :aria-pressed="showPassword"
                @click="showPassword = !showPassword"
              >
                <Icon :name="showPassword ? 'eye-off' : 'eye'" :size="16" />
              </button>
            </div>
            <p v-if="errors.password" class="mt-1 text-xs text-danger">{{ errors.password }}</p>
          </div>
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
          <button
            type="button"
            role="switch"
            :aria-checked="form.enabled"
            class="flex items-center justify-between gap-3 rounded-xl border border-ink/10 bg-cloud/60 px-4 py-3 text-sm transition hover:border-ink/20"
            :class="form.enabled ? 'text-ink-soft' : 'text-ink-muted'"
            @click="form.enabled = !form.enabled"
          >
            <span>账号{{ form.enabled ? '启用' : '停用' }}</span>
            <span
              class="relative h-5 w-9 shrink-0 rounded-full transition"
              :class="form.enabled ? 'bg-success' : 'bg-ink/25'"
            >
              <span
                class="absolute top-0.5 h-4 w-4 rounded-full bg-elevated shadow transition-all"
                :class="form.enabled ? 'left-[18px]' : 'left-0.5'"
              />
            </span>
          </button>

          <button
            type="button"
            class="flex items-center justify-center gap-1.5 rounded-xl border px-4 py-3 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-45"
            :class="verifyState === 'ok'
              ? 'border-success/30 bg-success/5 text-success'
              : 'border-brand/30 bg-brand/5 text-brand hover:bg-brand/10'"
            :disabled="verifying || !form.account || !form.password"
            @click="runVerify"
          >
            <span v-if="verifying" class="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-brand/30 border-t-brand" />
            <Icon v-else :name="verifyState === 'ok' ? 'check-circle' : 'user-check'" :size="14" />
            {{ verifyButtonText }}
          </button>
        </div>

        <p class="flex items-start gap-1.5 text-xs" :class="verifyView.tone">
          <Icon v-if="verifyView.icon" :name="verifyView.icon" :size="14" class="mt-px shrink-0" />
          <span>{{ verifyView.text }}</span>
        </p>
      </section>

      <!-- 推送凭证：账号级归属。凭证属于账号本身，配置套只决定「用不用它」 -->
      <section>
        <div class="mb-2 flex items-center gap-2">
          <span class="text-[11px] font-semibold tracking-wider text-ink-muted uppercase">推送去向</span>
          <span class="h-px flex-1 bg-ink/10" />
          <!-- 状态只留一处：每行左侧的落位竖线已经逐通道说明了状态，这里不再放第二套指示器 -->
          <span class="text-[11px] text-ink-muted">
            {{ filledCount ? `已配置 ${filledCount} 个通道` : '未配置 · 跟随配置套' }}
          </span>
        </div>

        <ul class="divide-y divide-ink/5">
          <li
            v-for="ch in channelRows"
            :key="ch"
            :class="ch === GROUP_KEY ? 'py-3 pl-3.5' : 'cred-row relative py-3 pl-3.5'"
          >
            <!-- 其它通道组头：常驻一行摘要，收起时它就是这一组的状态；展开后才列出两行完整配置 -->
            <button
              v-if="ch === GROUP_KEY"
              type="button"
              class="flex w-full items-center gap-2.5 text-left"
              :aria-expanded="secondaryOpen"
              @click="secondaryOpen = !secondaryOpen"
            >
              <span class="flex shrink-0 gap-1">
                <span
                  v-for="sec in SECONDARY_CHANNELS"
                  :key="'g' + sec"
                  class="grid h-6 w-6 place-items-center rounded-md text-[10px] font-bold"
                  :class="entryFilled(sec) ? channelTone(sec) : 'bg-ink/5 text-ink-muted'"
                >{{ channelShort(sec) }}</span>
              </span>
              <span class="min-w-0 truncate text-[13px] text-ink-soft">{{ SECONDARY_NAMES }}</span>
              <span
                class="ml-auto shrink-0 text-[11px]"
                :class="secondaryFilled ? 'text-ink-soft' : 'text-ink-muted'"
              >{{ secondarySummary }}</span>
              <span class="flex shrink-0 items-center gap-1 text-xs font-medium text-brand">
                {{ secondaryOpen ? '收起' : '展开' }}
                <Icon name="chevron-down" :size="12" :class="secondaryOpen && 'rotate-180'" />
              </span>
            </button>

            <template v-else>
            <!-- 落位刻度线：已落位实线、未落位虚线，配合组头摘要即可扫出哪几个还没配 -->
            <span
              aria-hidden="true"
              class="absolute inset-y-0 left-0 w-0 border-l-2"
              :class="entryFilled(ch) ? 'border-brand' : 'border-dashed border-ink/15'"
            />

            <span class="flex min-w-0 items-center gap-2.5">
              <span class="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-[10px] font-bold" :class="channelTone(ch)">
                {{ channelShort(ch) }}
              </span>
              <span class="truncate text-[13px] text-ink-soft">{{ channelLabel(ch) }}</span>
            </span>

            <span class="flex min-w-0 items-center gap-1.5">
              <BaseSelect
                v-if="hasOwnCreds(ch)"
                :model-value="form.pushCreds[ch].credId"
                :options="credOptionsOf(ch)"
                placement="auto"
                placeholder="跟随配置套"
                size="sm"
                class="min-w-0 flex-1"
                @update:model-value="(v) => (form.pushCreds[ch].credId = v)"
              />
              <button
                v-else
                type="button"
                class="flex min-w-0 flex-1 items-center justify-center gap-1 rounded-xl border border-dashed px-3 py-2 text-xs font-medium transition"
                :class="openFor(ch) ? 'border-brand/50 bg-brand/10 text-brand' : 'border-brand/40 bg-brand/5 text-brand hover:bg-brand/10'"
                @click="toggleInlineNew(ch)"
              >
                <Icon name="plus" :size="13" />新建凭证
              </button>
              <!-- 已有凭证时仍可就地再加一份，不必绕去资源池 -->
              <button
                v-if="hasOwnCreds(ch)"
                type="button"
                class="grid h-[38px] w-[38px] shrink-0 place-items-center rounded-xl border border-dashed transition"
                :class="openFor(ch)
                  ? 'border-brand/50 bg-brand/10 text-brand'
                  : 'border-ink/15 text-ink-muted hover:border-brand/40 hover:bg-brand/5 hover:text-brand'"
                :aria-label="`新建${channelLabel(ch)}凭证`"
                @click="toggleInlineNew(ch)"
              >
                <Icon name="plus" :size="14" />
              </button>
            </span>

            <!-- 收件人：与框内其它字段同构（标签在控件上方），与凭证选择正交——不绑凭证也能单独指定发给谁 -->
            <div v-if="ch === 'email'" class="cred-sub">
              <label class="mb-1.5 block text-sm font-medium text-ink-soft" for="acc-push-email-to">收件人</label>
              <input
                id="acc-push-email-to"
                v-model.trim="form.pushCreds.email.to"
                type="text"
                autocomplete="off"
                placeholder="可填多个，逗号分隔"
                class="login-input"
              />
              <p class="mt-1 text-xs" :class="recipientWarn ? 'text-warning' : 'text-ink-muted'">{{ recipientHint }}</p>
            </div>

            <!-- 就地新建凭证：省掉「先去我的资源建好再回来下拉」这一趟，也不丢已填内容 -->
            <div v-if="openFor(ch)" class="col-span-2 mt-2 rounded-xl bg-cloud/50 p-3.5">
              <div class="flex items-center justify-between gap-2">
                <p class="text-xs font-medium text-ink-soft">新建{{ channelLabel(ch) }}凭证</p>
                <button type="button" class="text-xs text-ink-muted transition hover:text-ink" @click="inlineNew = null">取消</button>
              </div>
              <div class="mt-3 space-y-3">
                <div>
                  <label class="mb-1.5 block text-xs text-ink-muted" for="inline-cred-name">凭证名称</label>
                  <input
                    id="inline-cred-name"
                    v-model.trim="inlineNew.name"
                    type="text"
                    autocomplete="off"
                    maxlength="64"
                    placeholder="如 我的 QQ 邮箱"
                    class="w-full rounded-xl border border-ink/10 bg-elevated px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
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
            </template>
          </li>
        </ul>

        <p class="mt-3 text-xs leading-relaxed text-ink-muted">
          可以全部留空——签到照常执行，只是不发通知；留空的通道跟随配置套里的凭证。
        </p>
        <p class="mt-1 text-xs leading-relaxed text-ink-muted">
          这里选的凭证只在任务凭证来源为「账号自带凭证」时生效，收件人不受这个限制。
        </p>
      </section>

      <!-- 平台档案（B 平台回填，用户不可改，故用内嵌只读块而非输入框） -->
      <section>
        <div class="mb-2 flex items-center gap-2">
          <span class="text-[11px] font-semibold tracking-wider text-ink-muted uppercase">平台档案</span>
          <span class="h-px flex-1 bg-ink/10" />
          <span class="inline-flex items-center gap-1 text-[11px] text-ink-muted">
            <Icon name="lock" :size="12" />校验通过后自动回填
          </span>
        </div>
        <dl class="grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl bg-cloud/50 px-3.5 py-3 sm:grid-cols-3">
          <div v-for="f in PROFILE_FIELDS" :key="f.key" class="min-w-0">
            <dt class="text-[11px] text-ink-muted">{{ f.label }}</dt>
            <dd
              class="mt-0.5 truncate text-sm"
              :class="form.profile[f.key] ? 'text-ink' : 'text-ink/30'"
              :title="form.profile[f.key] || ''"
            >
              {{ form.profile[f.key] || '—' }}
            </dd>
          </div>
        </dl>
      </section>
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

// 平台档案只读读数的展示顺序与名称（字段键与后端 map_student_info 一致）
const PROFILE_FIELDS = [
  { key: 'name', label: '姓名' },
  { key: 'studentNo', label: '学号' },
  { key: 'college', label: '学院' },
  { key: 'major', label: '专业' },
  { key: 'className', label: '班级' }
]

// 凭证池里可选的推送凭证（按通道分组），随弹窗打开时拉取
const credentials = ref([])
const creatingCred = ref(false)
// 就地新建凭证的草稿：{ channel, name, fields }，同一时刻只开一个
const inlineNew = ref(null)
// 密码明文开关：每次打开弹窗都回到掩码态，不跨会话记住
const showPassword = ref(false)

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

const filledCount = computed(() => PUSH_CHANNELS.filter((ch) => entryFilled(ch)).length)

// 版面把通道分两级：邮箱是绝大多数用户的主路径，占一整行；另外两个收进一组、默认收起。
// 组头在渲染序列里占一个哨兵位，所以用 GROUP_KEY 而不是通道码——列表里出现的都是字符串 key。
const PRIMARY_CHANNEL = 'email'
const SECONDARY_CHANNELS = PUSH_CHANNELS.filter((ch) => ch !== PRIMARY_CHANNEL)
const SECONDARY_NAMES = SECONDARY_CHANNELS.map(channelLabel).join(' · ')
const GROUP_KEY = '__secondary__'
const secondaryOpen = ref(false)

// 渲染序列：主通道 → 组头 →（展开时）组内各行
const channelRows = computed(() => (
  secondaryOpen.value
    ? [PRIMARY_CHANNEL, GROUP_KEY, ...SECONDARY_CHANNELS]
    : [PRIMARY_CHANNEL, GROUP_KEY]
))

const secondaryFilled = computed(() => SECONDARY_CHANNELS.filter((ch) => entryFilled(ch)).length)
// 收起时组头要能替代两行的信息：谁配过就直接点名，免得用户以为配置丢了
const secondarySummary = computed(() => {
  const hits = SECONDARY_CHANNELS.filter((ch) => entryFilled(ch))
  return hits.length ? `已配置 ${hits.map(channelLabel).join('、')}` : '未配置'
})

// 该通道是否已有落位内容（绑了凭证或单独指定了收件人）——落位竖线与汇总计数共用同一判定
function entryFilled(ch) {
  const e = form.pushCreds[ch]
  return !!(e.credId || e.to)
}

function hasOwnCreds(ch) {
  return credentials.value.some((c) => c.type === ch)
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

const openFor = (ch) => !!inlineNew.value && inlineNew.value.channel === ch

function toggleInlineNew(ch) {
  inlineNew.value = openFor(ch) ? null : { channel: ch, name: '', fields: blankFields() }
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

// 所选邮箱凭证的默认收件人：作为留空时的回落说明，写进提示而不是输入框占位
const emailFallback = computed(() => {
  const hit = credentials.value.find((c) => c.id === form.pushCreds.email.credId)
  return ((hit && hit.fields && hit.fields.emailTo) || '').trim()
})

// 提示分三态：没选凭证（留空＝跟随配置套）／选了且有默认收件人／选了但这份凭证没写默认收件人。
// 此前三态压成一句「留空时这里必填」，没选凭证时也在报警示色，读起来像整块必填。
const recipientHint = computed(() => {
  if (!form.pushCreds.email.credId) return '留空则跟随配置套的邮件凭证'
  if (emailFallback.value) return `留空则发给凭证默认收件人（${emailFallback.value}）`
  return '这份凭证没填默认收件人，这里要填一个'
})
// 只有「选了凭证、凭证又没有默认收件人、这里也没填」才是真会发不出去，此时才转警示色
const recipientWarn = computed(() =>
  !!form.pushCreds.email.credId && !emailFallback.value && !form.pushCreds.email.to
)

const verifyButtonText = computed(() => {
  if (verifyState.value === 'checking') return '校验中…'
  return verifyState.value === 'ok' ? '重新校验' : '校验账号'
})

// 校验行承载三种结论；idle 时它说的是一句说明——保存本就会自动校验，免得用户以为必须先点按钮
const verifyView = computed(() => {
  if (verifyState.value === 'checking') return { text: '正在校验账号密码…', tone: 'text-ink-soft', icon: '' }
  if (verifyState.value === 'ok') return { text: verifyMsg.value || '校验通过', tone: 'text-success', icon: 'check-circle' }
  if (verifyState.value === 'fail') return { text: verifyMsg.value || '校验失败', tone: 'text-danger', icon: 'alert' }
  return {
    text: props.mode === 'add' ? '保存时自动校验账号密码，通过后回填平台档案' : '改密码后保存会自动校验',
    tone: 'text-ink-muted',
    icon: ''
  }
})

function resetForm() {
  Object.assign(form, emptyForm())
  errors.account = ''
  errors.password = ''
  verifyState.value = 'idle'
  verifyMsg.value = ''
  inlineNew.value = null
  showPassword.value = false
  secondaryOpen.value = false
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

// 账号或密码一改，上一次的校验结论就失效——免得带着旧结论直接保存
function onCredentialInput(field) {
  errors[field] = ''
  if (verifyState.value !== 'idle') {
    verifyState.value = 'idle'
    verifyMsg.value = ''
  }
}

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

// 校验成功后从 B 平台档案自动回填（预检已缓存 profile，此处即时返回；字段保持只读）
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

// watch 一律写在脚本末尾：注册时会立刻求一次源值，写在依赖声明之前会触发 TDZ，
// setup 抛错会导致整个组件不渲染（eslint/build 都查不出）
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

defineExpose({ close })
</script>

<style scoped>
/* 密码框关掉浏览器自带的显示按钮：规则已提到 assets/main.css 的 `.pwd-input`，
   与登录页共用一份；在自带显示开关的密码框上加这个类即可。 */

/* 通道行两列：左列是通道标识（移动端按内容宽、sm 起固定宽以便各行对齐），右列是控件。
   标识与控件各占一格，"哪个通道 / 配了什么"在同一条水平线上对读。 */
.cred-row {
  display: grid;
  grid-template-columns: minmax(0, auto) minmax(0, 1fr);
  align-items: center;
  column-gap: 0.75rem;
}

/* 收件人这类附属于某通道行的字段：跨两列自成一块，标签落在控件上方。
   别把它放回左侧标识列参与居中——那一列是对着「控件 + 下方提示」整块居中的，
   提示行一出现标签就整体下沉半行（实测差 10px），看着就是没对齐。 */
.cred-sub {
  grid-column: 1 / -1;
  margin-top: 0.75rem;
}

/* sm 起标识列固定宽，附属块跟着缩进到控件列、与上方控件左缘对齐（缩进 = 7.5rem + 0.75rem） */
@media (min-width: 640px) {
  .cred-row {
    grid-template-columns: 7.5rem minmax(0, 1fr);
  }
  .cred-sub {
    margin-left: 8.25rem;
  }
}
</style>
