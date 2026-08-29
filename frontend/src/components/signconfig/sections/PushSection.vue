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
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-ink/10 px-3 text-sm text-ink-soft transition hover:bg-cloud"
              @click="store.gotoResource('credentials')"
            >
              <Icon name="send" :size="14" />管理凭证
            </button>
            <div class="inline-flex rounded-xl bg-cloud p-1 text-sm">
              <button
                type="button"
                class="rounded-lg px-3 py-1 font-medium transition"
                :class="config.push.useOwnCredential ? 'bg-white text-brand shadow-sm' : 'text-ink-muted'"
                @click="config.push.useOwnCredential = true"
              >
                回填我的凭证
              </button>
              <button
                type="button"
                class="rounded-lg px-3 py-1 font-medium transition"
                :class="!config.push.useOwnCredential ? 'bg-white text-brand shadow-sm' : 'text-ink-muted'"
                @click="config.push.useOwnCredential = false"
              >
                直接填写
              </button>
            </div>
          </div>
        </div>

        <!-- 回填我的凭证：每个已选通道各绑一个同类型凭证，支持多通道同时推送 -->
        <GCollapse :show="config.push.useOwnCredential">
          <div class="pt-3">
            <p v-if="selectedChannels.length === 0" class="rounded-xl border border-dashed border-ink/15 px-3 py-3 text-center text-xs text-ink-muted">
              请先在上方选择推送通道，再为各通道绑定凭证
            </p>
            <div v-else class="space-y-2">
              <p class="text-xs text-ink-muted">为每个通道分别绑定凭证，多通道会同时推送。</p>
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

        <!-- 直接填写：只渲染已选通道对应的字段 -->
        <GCollapse :show="!config.push.useOwnCredential">
          <div class="pt-3">
            <p v-if="selectedChannels.length === 0" class="rounded-xl border border-dashed border-ink/15 px-3 py-3 text-center text-xs text-ink-muted">
              请先在上方选择推送通道，再填写对应密钥
            </p>
            <div v-else class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <input v-if="config.push.channels.includes('serverchan')" v-model="config.push.cred.serverchanKey" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="Server酱 SendKey" />
              <input v-if="config.push.channels.includes('pushplus')" v-model="config.push.cred.pushplusToken" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="PushPlus Token" />
              <input v-if="config.push.channels.includes('email')" v-model="config.push.cred.emailSmtp" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="SMTP 地址" />
              <input v-if="config.push.channels.includes('email')" v-model="config.push.cred.emailFrom" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="发件人" />
              <input v-if="config.push.channels.includes('email')" v-model="config.push.cred.emailPass" type="password" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="授权码" />
              <input v-if="config.push.channels.includes('email')" v-model="config.push.cred.emailTo" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="收件人" />
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
            :class="config.push.template === t.value ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
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
import { useSignConfigStore } from '@/stores/signConfig'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' }
})

const store = useSignConfigStore()
const CHANNELS = ['serverchan', 'pushplus', 'email']
const templateOptions = [
  { label: 'HTML', value: 'html' },
  { label: 'TXT', value: 'txt' },
  { label: 'Markdown', value: 'markdown' }
]

// 补齐 credIds 结构，并兼容早期"单一 credId"数据：按凭证类型归位到对应通道
function ensureCredIds(cfg) {
  const push = cfg && cfg.push
  if (!push) return
  if (!push.credIds || typeof push.credIds !== 'object') push.credIds = {}
  for (const ch of CHANNELS) if (!(ch in push.credIds)) push.credIds[ch] = null
  if (!push.template || !templateOptions.some((t) => t.value === push.template)) push.template = 'html'
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

function channelLabel(v) {
  const hit = store.channelOptions.find((c) => c.value === v)
  return hit ? hit.label : v
}
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
