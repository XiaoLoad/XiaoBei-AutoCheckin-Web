<template>
  <ConfigSection title="推送配置" icon="send" :source="source">
    <div class="space-y-3">
      <!-- 01 推给谁：通道是入口，勾谁就为谁做核对 -->
      <div>
        <div class="mb-1.5 flex items-center gap-1.5">
          <span class="text-[11px] font-medium tabular-nums text-ink-muted">01</span>
          <span class="text-xs font-medium text-ink">推给谁</span>
          <span class="ml-auto text-[11px] text-ink-muted">{{ channelAside }}</span>
        </div>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="c in store.channelOptions"
            :key="c.value"
            type="button"
            class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition"
            :class="isOn(c.value) ? 'border-brand bg-brand/10 text-brand' : 'border-ink/10 text-ink-muted hover:bg-cloud'"
            :aria-pressed="isOn(c.value)"
            @click="toggleChannel(c.value)"
          >
            <span class="h-1.5 w-1.5 rounded-full" :class="isOn(c.value) ? channelDot(c.value) : 'bg-ink/20'" />
            {{ c.label }}
          </button>
        </div>
      </div>

      <template v-if="selectedChannels.length">
        <!-- 02 用谁的凭证：两档。各账号自带是主路径，整套共用退为兜底 -->
        <div>
          <div class="mb-1.5 flex items-center gap-1.5">
            <span class="text-[11px] font-medium tabular-nums text-ink-muted">02</span>
            <span class="text-xs font-medium text-ink">用谁的凭证</span>
          </div>
          <div class="inline-flex w-full rounded-lg bg-cloud p-0.5" role="group" aria-label="凭证来源">
            <button
              v-for="s in SCOPES"
              :key="s.value"
              type="button"
              class="flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition"
              :class="credSource === s.value ? 'bg-elevated text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
              :aria-pressed="credSource === s.value"
              @click="credSource = s.value"
            >
              {{ s.label }}
            </button>
          </div>
          <p class="mt-1.5 text-xs text-ink-muted">{{ scopeHint }}</p>

          <!-- 第二层只在「整套共用」下才有意义：凭证从资源池取还是当场填 -->
          <div v-if="credSource === 'shared'" class="xb-block-in mt-2 flex flex-wrap items-center gap-2">
            <span class="text-xs text-ink-muted">凭证来自</span>
            <div class="inline-flex rounded-lg bg-cloud p-0.5" role="group" aria-label="共用凭证来源">
              <button
                v-for="m in POOL_MODES"
                :key="m.value"
                type="button"
                class="rounded-md px-2.5 py-1 text-xs font-medium transition"
                :class="poolMode === m.value ? 'bg-elevated text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
                :aria-pressed="poolMode === m.value"
                @click="poolMode = m.value"
              >
                {{ m.label }}
              </button>
            </div>
            <button
              v-if="poolMode === 'mine'"
              type="button"
              class="ml-auto inline-flex items-center gap-1 text-xs font-medium text-brand transition hover:text-brand-dark"
              @click="store.gotoResource('credentials')"
            >
              <Icon name="layers" :size="13" />凭证池
            </button>
          </div>
        </div>

        <!-- 03 逐通道落位：每行自带状态，不用展开任何东西就能看出哪个通道送不到 -->
        <div>
          <div class="mb-1.5 flex items-center gap-1.5">
            <span class="text-[11px] font-medium tabular-nums text-ink-muted">03</span>
            <span class="text-xs font-medium text-ink">{{ step3.title }}</span>
            <span class="ml-auto text-[11px] text-ink-muted">{{ step3.aside }}</span>
          </div>
          <div class="divide-y divide-ink/5 rounded-xl border border-ink/10 px-3">
            <PushChannelRow
              v-for="ch in selectedChannels"
              :key="ch"
              :channel="ch"
              :state="rowState(ch)"
            >
              <!-- 各账号自带：只回答「谁没落位」，token 型漏网时摆兜底 -->
              <PushEmailRow
                v-if="bodyMode === 'audit' && ch === 'email'"
                :audit="rowState(ch)"
                :scope="isAccountScope ? 'account' : 'set'"
                :options="store.credentialOptionsByChannel.email"
                :picker-value="fallbackIdOf('email')"
                @update:model-value="(v) => setCredId('email', v)"
                @create="store.gotoResource('credentials')"
              />
              <template v-if="bodyMode === 'audit' && ch !== 'email'">
                <div v-if="rowState(ch).dangling" class="flex flex-wrap items-center gap-2">
                  <button
                    v-if="!isAdmin"
                    type="button"
                    class="inline-flex items-center gap-1.5 rounded-lg border border-ink/10 px-2.5 py-1.5 text-[11px] text-ink-soft transition hover:bg-cloud"
                    @click="router.push('/accounts')"
                  >
                    <Icon name="user" :size="13" />去账号管理重绑
                  </button>
                </div>
                <div v-else-if="rowState(ch).leak" class="flex flex-wrap items-center gap-2">
                  <span class="shrink-0 text-[11px] text-ink-muted">兜底</span>
                  <PushCredPick
                    :model-value="fallbackIdOf(ch)"
                    :options="fallbackOptions(ch)"
                    placeholder="不设兜底"
                    :empty-text="`暂无${channelLabel(ch)}凭证，去新建`"
                    @update:model-value="(v) => setCredId(ch, v)"
                    @create="store.gotoResource('credentials')"
                  />
                </div>
              </template>

              <!-- 整套共用·我的资源：逐通道各绑一份同类型凭证 -->
              <PushCredPick
                v-if="bodyMode === 'pick'"
                :model-value="credIdOf(ch)"
                :options="store.credentialOptionsByChannel[ch]"
                :empty-text="`暂无${channelLabel(ch)}凭证，去新建`"
                @update:model-value="(v) => setCredId(ch, v)"
                @create="store.gotoResource('credentials')"
              />

              <!-- 整套共用·直接填写：字段定义与凭证弹窗共用同一组件 -->
              <div v-if="bodyMode === 'inline'" class="pt-0.5">
                <PushCredentialFields v-model="config.push.cred" :channel="ch" />
              </div>
            </PushChannelRow>
          </div>
        </div>

        <!-- 内容与时机：与凭证无关的两件事并排，省掉两段各自的长说明 -->
        <div class="border-t border-ink/5 pt-2.5">
          <div class="flex flex-wrap items-start gap-x-5 gap-y-2.5">
            <div>
              <p class="mb-1 text-[11px] text-ink-muted">推送内容</p>
              <div class="inline-flex rounded-lg bg-cloud p-0.5" role="group" aria-label="推送模板">
                <button
                  v-for="t in templateOptions"
                  :key="t.value"
                  type="button"
                  class="rounded-md px-2.5 py-1 text-xs font-medium transition"
                  :class="config.push.template === t.value ? 'bg-elevated text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
                  :aria-pressed="config.push.template === t.value"
                  @click="config.push.template = t.value"
                >
                  {{ t.label }}
                </button>
              </div>
            </div>
            <div>
              <p class="mb-1 text-[11px] text-ink-muted">哪些状态要推</p>
              <div class="flex items-center gap-3">
                <label v-for="n in NOTIFY" :key="n.key" class="flex items-center gap-1.5 text-xs text-ink-soft">
                  {{ n.label }}<ConfigToggle v-model="config.push.notify[n.key]" />
                </label>
              </div>
            </div>
          </div>
          <p class="mt-2 text-[11px] text-ink-muted">HTML 为卡片样式，TXT / Markdown 为纯文本（图片不展示）；单条内容上限 2 万字。</p>
        </div>
      </template>

      <p v-else class="rounded-xl border border-dashed border-ink/15 px-3 py-3 text-center text-xs text-ink-muted">
        勾选通道后，这里会逐通道核对能不能送到
      </p>
    </div>
  </ConfigSection>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import ConfigToggle from '@/components/signconfig/ConfigToggle.vue'
import Icon from '@/components/Icon.vue'
import PushCredentialFields from '@/components/PushCredentialFields.vue'
import PushChannelRow from '@/components/signconfig/sections/push/PushChannelRow.vue'
import PushCredPick from '@/components/signconfig/sections/push/PushCredPick.vue'
import PushEmailRow from '@/components/signconfig/sections/push/PushEmailRow.vue'
import { useAuthStore } from '@/stores/auth'
import { useSignConfigStore } from '@/stores/signConfig'
import { PUSH_CHANNELS, channelDot, channelLabel } from '@/utils/pushChannels'
import {
  accountRecipient,
  auditAccountChannel,
  auditAccountEmail,
  auditEmailChannel,
  auditTokenChannel,
  emailToOf
} from '@/utils/pushAudit'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' },
  // 语境：'set' 编辑配置套（模板视角，出逐通道统计）/ 'account' 编辑某个账号的任务。
  // ⚠️用显式 prop 而不是「有没有传 account 对象」来判：后者在账号暂时解析不到时会静默退回
  // 配置套视角，把其它账号的绑定情况摆给单账号看——那正是账号语境不该出现的东西。
  scope: { type: String, default: 'set' },
  // 账号上下文的对象：scope='account' 时用来解析这一个账号的处境
  account: { type: Object, default: null }
})

const store = useSignConfigStore()
const auth = useAuthStore()
const router = useRouter()
const isAdmin = computed(() => auth.isAdmin)

const CHANNELS = PUSH_CHANNELS
const templateOptions = [
  { label: 'HTML', value: 'html' },
  { label: 'TXT', value: 'txt' },
  { label: 'Markdown', value: 'markdown' }
]
const NOTIFY = [
  { key: 'success', label: '成功' },
  { key: 'skip', label: '跳过' },
  { key: 'fail', label: '失败' }
]
const SCOPES = [
  { value: 'account', label: '按账号各自' },
  { value: 'shared', label: '整套共用一份' }
]
const POOL_MODES = [
  { value: 'mine', label: '我的资源' },
  { value: 'inline', label: '直接填写' }
]
const KEY_FIELD = { serverchan: 'serverchanKey', pushplus: 'pushplusToken' }

// 按 channelOptions 的顺序输出已选通道，避免点选顺序影响展示顺序
const selectedChannels = computed(() =>
  store.channelOptions.map((c) => c.value).filter((v) => props.config.push.channels.includes(v))
)
const isOn = (v) => props.config.push.channels.includes(v)

const isAccountScope = computed(() => props.scope === 'account')
// 账号语境的对象：优先用调用方传进来的；没传就按当前选中账号兜底解析，仍解析不到则保持
// 账号语境并显示「未解析到账号」，绝不退回配置套口径
const account = computed(() => {
  if (!isAccountScope.value) return null
  if (props.account) return props.account
  return store.accounts.find((a) => String(a.id) === String(store.selectedAccountId)) || null
})
const enabledAccounts = computed(() => store.accounts.filter((a) => a.status !== 'disabled'))
// 邮件收件邮箱另填的账号数（只在配置套视角下有意义，账号视角不出现账号维度的统计）
const extraRecipients = computed(() =>
  isAccountScope.value ? 0 : enabledAccounts.value.filter((a) => accountRecipient(a, 'email')).length
)

// 配置里仍是两个互斥开关：来源只切 useAccountCredential，共用下的取用方式切 useOwnCredential。
// 这样切回来时能记住上一档选的是资源池还是直接填写
const credSource = computed({
  get() {
    return props.config.push.useAccountCredential ? 'account' : 'shared'
  },
  set(v) {
    props.config.push.useAccountCredential = v === 'account'
  }
})
const poolMode = computed({
  get() {
    return props.config.push.useOwnCredential ? 'mine' : 'inline'
  },
  set(v) {
    props.config.push.useOwnCredential = v === 'mine'
  }
})

const scopeHint = computed(() => {
  if (credSource.value === 'account') {
    return '取执行账号在账号管理里绑定的凭证；它没绑的通道回落下面的兜底。'
  }
  return poolMode.value === 'mine'
    ? '整个配置套共用选定的凭证。'
    : '整个配置套共用这里填写的密钥，随配置一起保存。'
})
const channelAside = computed(() =>
  selectedChannels.value.length ? `已选 ${selectedChannels.value.length} 个` : '可多选'
)

function credById(id) {
  if (!id) return null
  return store.credentials.find((c) => String(c.id) === String(id)) || null
}
function fallbackIdOf(ch) {
  return (props.config.push.credIds && props.config.push.credIds[ch]) || ''
}
// 兜底可空：不设就是让这些账号跳过本次推送，不是错误状态，故给一个显式的清空项
function fallbackOptions(ch) {
  return [{ label: '不设兜底', value: '' }, ...(store.credentialOptionsByChannel[ch] || [])]
}

// 共用模式下账号只影响邮件收件邮箱（账号自填覆盖凭证默认值），与后端 use_own 分支一致
function sharedRecipient(account) {
  const cred =
    poolMode.value === 'mine'
      ? credById((props.config.push.credIds || {}).email)
      : { fields: props.config.push.cred || {} }
  return accountRecipient(account, 'email') || emailToOf(cred)
}

// 共用/直接填写下的行状态＝这一行本身齐不齐备（与账号绑定无关）
function sharedState(ch) {
  const push = props.config.push
  if (poolMode.value === 'mine') {
    const cred = credById((push.credIds || {})[ch])
    if (!cred) return { state: 'gap', text: '未选凭证', detail: '' }
    if (ch !== 'email') return { state: 'ok', text: '已就绪', detail: `用「${cred.name}」发送` }
    const to = emailToOf(cred)
    if (!to) return { state: 'gap', text: '凭证缺收件邮箱', detail: '这份凭证没填默认收件邮箱' }
    return {
      state: 'ok',
      text: '已就绪',
      detail: extraRecipients.value
        ? `默认收件邮箱 ${to} · ${extraRecipients.value} 个账号另填收件邮箱`
        : `默认收件邮箱 ${to}`
    }
  }
  const c = push.cred || {}
  if (ch !== 'email') {
    return (c[KEY_FIELD[ch]] || '').trim()
      ? { state: 'ok', text: '已就绪', detail: '' }
      : { state: 'gap', text: '缺密钥', detail: '' }
  }
  // 内联邮件的收件邮箱也可以由账号自填覆盖，两边都空才是真发不出去
  if (isAccountScope.value) {
    if (!c.emailSmtp || !c.emailFrom) return { state: 'gap', text: '缺 SMTP / 发件邮箱', detail: '' }
    return sharedRecipient(account.value)
      ? { state: 'ok', text: '会送达', detail: '' }
      : { state: 'gap', text: '缺收件邮箱', detail: '本账号没自填，这里也没填默认收件邮箱' }
  }
  const to = (c.emailTo || '').trim()
  if (!c.emailSmtp || !c.emailFrom) return { state: 'gap', text: '缺 SMTP / 发件邮箱', detail: '' }
  if (!to && !extraRecipients.value) {
    return { state: 'gap', text: '缺收件邮箱', detail: '这里没填，也没有账号单独指定收件邮箱' }
  }
  return { state: 'ok', text: '已就绪', detail: to ? `默认收件邮箱 ${to}` : '收件邮箱由各账号自填' }
}

const bodyMode = computed(() => {
  if (credSource.value === 'account') return 'audit'
  return poolMode.value === 'mine' ? 'pick' : 'inline'
})

const audit = computed(() => {
  const out = {}
  for (const ch of selectedChannels.value) {
    if (bodyMode.value !== 'audit') {
      out[ch] = sharedState(ch)
      continue
    }
    if (ch === 'email') {
      out[ch] = isAccountScope.value
        ? auditAccountEmail(account.value, credById(fallbackIdOf('email')), credById)
        : auditEmailChannel(enabledAccounts.value, credById(fallbackIdOf('email')), credById)
      continue
    }
    out[ch] = isAccountScope.value
      ? auditAccountChannel(ch, account.value, credById(fallbackIdOf(ch)), credById)
      : auditTokenChannel(ch, enabledAccounts.value, credById(fallbackIdOf(ch)))
  }
  return out
})
const rowState = (ch) => audit.value[ch] || { state: 'idle', text: '—' }

const step3 = computed(() => {
  if (bodyMode.value === 'audit') {
    return {
      title: isAccountScope.value ? '本账号落位' : '落位核对',
      aside: isAccountScope.value ? account.value?.name || '未解析到账号' : `共 ${enabledAccounts.value.length} 个账号`
    }
  }
  return {
    title: bodyMode.value === 'pick' ? '共用凭证' : '直接填写',
    aside: `${selectedChannels.value.length} 个通道`
  }
})

// 补齐 credIds / cred / notify 结构，并兼容早期「单一 credId」数据：按凭证类型归位到对应通道
function ensureCredIds(cfg) {
  const push = cfg && cfg.push
  if (!push) return
  if (!push.credIds || typeof push.credIds !== 'object') push.credIds = {}
  for (const ch of CHANNELS) if (!(ch in push.credIds)) push.credIds[ch] = null
  if (!push.cred || typeof push.cred !== 'object') push.cred = {}
  if (!push.notify || typeof push.notify !== 'object') {
    push.notify = { success: true, skip: true, fail: true }
  }
  if (!push.template || !templateOptions.some((t) => t.value === push.template)) push.template = 'html'
  // 老配置没有该开关：显式落成 false，保证保存时字段完整、语义不变
  if (typeof push.useAccountCredential !== 'boolean') push.useAccountCredential = false
  if (push.credId) {
    const hit = store.credentials.find((c) => c.id === push.credId)
    if (hit && CHANNELS.includes(hit.type) && !push.credIds[hit.type]) push.credIds[hit.type] = push.credId
    delete push.credId
  }
}

function toggleChannel(v) {
  const list = props.config.push.channels
  const i = list.indexOf(v)
  if (i === -1) {
    list.push(v)
  } else {
    list.splice(i, 1)
    // 取消通道时清掉其凭证绑定与兜底，避免保存脏数据
    if (props.config.push.credIds) props.config.push.credIds[v] = null
  }
}
// credIds[通道] 在两处写入：整套共用时是这一通道要用的凭证，各账号自带时是未绑账号的兜底
function credIdOf(ch) {
  return (props.config.push.credIds && props.config.push.credIds[ch]) || ''
}
function setCredId(ch, v) {
  props.config.push.credIds[ch] = v || null
}

watch(() => props.config, ensureCredIds, { immediate: true })
// 凭证池异步加载完成后再兜一次，保证旧数据的类型归位能命中
watch(() => store.credentials.length, () => ensureCredIds(props.config))
</script>
