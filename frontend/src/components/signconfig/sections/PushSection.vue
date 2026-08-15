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

        <BaseSelect
          v-if="config.push.useOwnCredential"
          v-model="credId"
          :options="store.credentialOptions"
          :searchable="true"
          placeholder="选择我的凭证"
          size="sm"
          class="mt-3 w-72"
        />

        <div v-else class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <input v-if="config.push.channels.includes('serverchan')" v-model="config.push.cred.serverchanKey" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="Server酱 SendKey" />
          <input v-if="config.push.channels.includes('pushplus')" v-model="config.push.cred.pushplusToken" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="PushPlus Token" />
          <input v-if="config.push.channels.includes('email')" v-model="config.push.cred.emailSmtp" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="SMTP 地址" />
          <input v-if="config.push.channels.includes('email')" v-model="config.push.cred.emailFrom" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="发件人" />
          <input v-if="config.push.channels.includes('email')" v-model="config.push.cred.emailPass" type="password" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="授权码" />
          <input v-if="config.push.channels.includes('email')" v-model="config.push.cred.emailTo" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="收件人" />
        </div>
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
import { computed } from 'vue'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import ConfigToggle from '@/components/signconfig/ConfigToggle.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import { useSignConfigStore } from '@/stores/signConfig'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' }
})

const store = useSignConfigStore()
const credId = computed({
  get: () => props.config.push.credId,
  set: (v) => (props.config.push.credId = v)
})

function toggleChannel(v) {
  const i = props.config.push.channels.indexOf(v)
  if (i === -1) props.config.push.channels.push(v)
  else props.config.push.channels.splice(i, 1)
}
</script>
