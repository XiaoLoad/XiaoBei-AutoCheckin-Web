<template>
  <ConfigSection title="推送配置" icon="send" :source="source">
    <div class="space-y-3">
      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-muted">推送通道（可多选）</label>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="c in store.channelOptions"
            :key="c.value"
            type="button"
            class="rounded-lg border px-3 py-1.5 text-sm transition"
            :class="config.push.channels.includes(c.value) ? 'border-brand bg-brand/10 text-brand' : 'border-ink/10 text-ink-soft hover:bg-cloud'"
            @click="toggleChannel(c.value)"
          >
            {{ c.label }}
          </button>
        </div>
      </div>

      <div class="rounded-lg border border-ink/10 p-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <p class="text-sm font-medium text-ink">凭证来源</p>
          <button
            v-if="credSource !== 'account'"
            type="button"
            class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-ink/10 px-3 text-sm text-ink-soft transition hover:bg-cloud"
            @click="store.gotoResource('credentials')"
          >
            <Icon name="send" :size="14" />管理凭证
          </button>
        </div>

        <!-- 三项互斥：来源不同，凭证归属层级就不同，用分段控件让语义一次看清 -->
        <div class="mt-2.5 inline-flex rounded-xl bg-cloud p-1 text-sm">
          <button
            v-for="s in CRED_SOURCES"
            :key="s.value"
            type="button"
            class="rounded-lg px-3 py-1 font-medium transition"
            :class="credSource === s.value ? 'bg-elevated text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
            @click="credSource = s.value"
          >
            {{ s.label }}
          </button>
        </div>

        <p class="mt-2 text-xs text-ink-muted">{{ sourceHint }}</p>

        <!-- 各账号自带：直接读一份账号绑定现状，先指出还没落位的账号，再交给用户去补 -->
        <GCollapse :show="credSource === 'account'">
          <div class="pt-3">
            <p v-if="accountBinding.length === 0" class="rounded-xl border border-dashed border-ink/15 px-3 py-3 text-center text-xs text-ink-muted">
              暂无 B 平台账号，请先在「账号管理」添加
            </p>
            <div v-else class="rounded-xl border border-ink/10 bg-cloud/40 px-3 py-2.5 text-xs">
              <p class="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span class="font-medium text-ink-soft">已配置 {{ boundAccountCount }} / {{ accountBinding.length }} 个账号</span>
                <span v-if="unboundAccounts.length" class="text-warning">
                  未配置：{{ unboundAccounts.slice(0, 3).join('、') }}<template v-if="unboundAccounts.length > 3"> 等 {{ unboundAccounts.length }} 个</template>
                </span>
                <span v-else class="inline-flex items-center gap-1 font-medium text-success">
                  <Icon name="check-circle" :size="13" />全部已配置
                </span>
              </p>
              <p class="mt-1.5 text-ink-muted">
                配置入口：账号管理 → 编辑账号 → 推送凭证（可只指定邮件收件人）。未配置的账号回落到套里的凭证，两者都没有则跳过该次推送（任务日志可查）。
              </p>
            </div>
          </div>
        </GCollapse>

        <!-- 回填我的凭证：每个已选通道各绑一个同类型凭证，支持多通道同时推送 -->
        <GCollapse :show="credSource === 'pool'">
          <div class="pt-3">
            <p v-if="selectedChannels.length === 0" class="rounded-xl border border-dashed border-ink/15 px-3 py-3 text-center text-xs text-ink-muted">
              请先在上方选择推送通道，再为各通道绑定凭证
            </p>
            <div v-else class="space-y-2">
              <p class="text-xs text-ink-muted">整套共用这几份凭证，多通道会同时推送。</p>
              <transition-group name="remark" tag="div" class="relative space-y-2">
                <div v-for="ch in selectedChannels" :key="ch" class="flex flex-wrap items-center gap-2">
                  <span class="w-20 shrink-0 rounded-lg bg-cloud px-2 py-1 text-center text-xs font-medium text-ink-soft">
                    {{ channelLabel(ch) }}
                  </span>
                  <BaseSelect
                    v-if="hasCredential(ch)"
                    :model-value="credIdOf(ch)"
                    :options="store.credentialOptionsByChannel[ch]"
                    :searchable="true"
                    placement="auto"
                    placeholder="选择凭证"
                    size="sm"
                    class="w-60"
                    @update:model-value="(v) => setCredId(ch, v)"
                  />
                  <button
                    v-else
                    type="button"
                    class="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-amber/40 bg-amber/10 px-3 py-1.5 text-xs text-amber transition hover:bg-amber/15"
                    @click="store.gotoResource('credentials')"
                  >
                    <Icon name="plus" :size="14" />暂无该类型凭证，去新建
                  </button>
                </div>
              </transition-group>
            </div>
          </div>
        </GCollapse>

        <!-- 直接填写：只渲染已选通道对应的字段（字段定义与凭证弹窗共用同一组件） -->
        <GCollapse :show="credSource === 'manual'">
          <div class="pt-3">
            <p v-if="selectedChannels.length === 0" class="rounded-xl border border-dashed border-ink/15 px-3 py-3 text-center text-xs text-ink-muted">
              请先在上方选择推送通道，再填写对应密钥
            </p>
            <div v-else class="space-y-3">
              <PushCredentialFields
                v-for="ch in selectedChannels"
                :key="ch"
                v-model="config.push.cred"
                :channel="ch"
              />
            </div>
          </div>
        </GCollapse>
      </div>

      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-muted">推送模板</label>
        <div class="inline-flex rounded-xl bg-cloud p-1">
          <button
            v-for="t in templateOptions"
            :key="t.value"
            type="button"
            class="rounded-lg px-3 py-1.5 text-sm font-medium transition"
            :class="config.push.template === t.value ? 'bg-elevated text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
            @click="config.push.template = t.value"
          >
            {{ t.label }}
          </button>
        </div>
        <p class="mt-1.5 text-xs text-ink-muted">HTML 优雅卡片（微信/pushplus 推荐）；TXT / Markdown 为纯文本，图片等富内容不展示。内容受 pushplus 长度限制（标题 ≤100 字、内容 ≤2 万字）。</p>
      </div>

      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-muted">各状态推送开关</label>
        <div class="flex flex-wrap gap-4">
          <label class="flex items-center gap-2 text-sm text-ink-soft">成功<ConfigToggle v-model="config.push.notify.success" /></label>
          <label class="flex items-center gap-2 text-sm text-ink-soft">跳过<ConfigToggle v-model="config.push.notify.skip" /></label>
          <label class="flex items-center gap-2 text-sm text-ink-soft">失败<ConfigToggle v-model="config.push.notify.fail" /></label>
        </div>
      </div>
    </div>
  </ConfigSection>
</template>

<script setup>
import { computed, watch } from 'vue'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import ConfigToggle from '@/components/signconfig/ConfigToggle.vue'
import GCollapse from '@/components/signconfig/GCollapse.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import Icon from '@/components/Icon.vue'
import PushCredentialFields from '@/components/PushCredentialFields.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { PUSH_CHANNELS, channelLabel, readCredEntry } from '@/utils/pushChannels'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' }
})

const store = useSignConfigStore()
const CHANNELS = PUSH_CHANNELS
const templateOptions = [
  { label: 'HTML', value: 'html' },
  { label: 'TXT', value: 'txt' },
  { label: 'Markdown', value: 'markdown' }
]

// 凭证来源三选：归属层级不同，所以互斥；分段控件让"凭证属于谁"一次看清
const CRED_SOURCES = [
  { value: 'account', label: '各账号自带' },
  { value: 'pool', label: '回填我的凭证' },
  { value: 'manual', label: '直接填写' }
]
const SOURCE_HINTS = {
  account: '按执行账号取它自己在账号管理里绑定的凭证与邮件收件人，一个配置套套用多个账号也不会串号。',
  pool: '整个配置套共用下方为各通道绑定的凭证。',
  manual: '整个配置套共用下方填写的密钥，随配置一起保存。'
}

// 三元组映射到配置里的两个开关：account 优先，其余按 useOwnCredential 分池/手填
const credSource = computed({
  get() {
    const push = props.config.push
    if (push.useAccountCredential) return 'account'
    return push.useOwnCredential ? 'pool' : 'manual'
  },
  set(v) {
    props.config.push.useAccountCredential = v === 'account'
    props.config.push.useOwnCredential = v === 'pool'
  }
})
const sourceHint = computed(() => SOURCE_HINTS[credSource.value] || '')

// 账号配置现状：绑了凭证或单独指定了收件人都算「已配置」，选「各账号自带」时直接点名没配的
const accountBinding = computed(() =>
  store.accounts.map((a) => ({
    name: a.name || a.account || String(a.id),
    configured: PUSH_CHANNELS.some((ch) => {
      const e = readCredEntry((a.pushCreds || {})[ch])
      return !!(e.credId || e.to)
    })
  }))
)
const boundAccountCount = computed(() => accountBinding.value.filter((a) => a.configured).length)
const unboundAccounts = computed(() => accountBinding.value.filter((a) => !a.configured).map((a) => a.name))

// 补齐 credIds 结构，并兼容早期"单一 credId"数据：按凭证类型归位到对应通道
function ensureCredIds(cfg) {
  const push = cfg && cfg.push
  if (!push) return
  if (!push.credIds || typeof push.credIds !== 'object') push.credIds = {}
  for (const ch of CHANNELS) if (!(ch in push.credIds)) push.credIds[ch] = null
  if (!push.cred || typeof push.cred !== 'object') push.cred = {}
  if (!push.template || !templateOptions.some((t) => t.value === push.template)) push.template = 'html'
  // 老配置没有该开关：显式落成 false，保证保存时字段完整、语义不变
  if (typeof push.useAccountCredential !== 'boolean') push.useAccountCredential = false
  if (push.credId) {
    const hit = store.credentials.find((c) => c.id === push.credId)
    if (hit && CHANNELS.includes(hit.type) && !push.credIds[hit.type]) push.credIds[hit.type] = push.credId
    delete push.credId
  }
}

watch(() => props.config, ensureCredIds, { immediate: true })
// 凭证池异步加载完成后再兜一次，保证旧数据的类型归位能命中
watch(() => store.credentials.length, () => ensureCredIds(props.config))

// 按 channelOptions 的顺序输出已选通道，避免点选顺序影响展示顺序
const selectedChannels = computed(() =>
  store.channelOptions.map((c) => c.value).filter((v) => props.config.push.channels.includes(v))
)

function hasCredential(ch) {
  return store.credentials.some((c) => c.type === ch)
}
function credIdOf(ch) {
  return (props.config.push.credIds && props.config.push.credIds[ch]) || ''
}
function setCredId(ch, v) {
  props.config.push.credIds[ch] = v || null
}

function toggleChannel(v) {
  const list = props.config.push.channels
  const i = list.indexOf(v)
  if (i === -1) {
    list.push(v)
  } else {
    list.splice(i, 1)
    // 取消通道时清掉其凭证绑定，避免保存脏数据
    if (props.config.push.credIds) props.config.push.credIds[v] = null
  }
}
</script>
