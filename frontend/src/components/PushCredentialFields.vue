<template>
  <!-- 单通道凭证字段组：凭证弹窗、账号弹窗就地新建、配置套直接填写共用一套字段定义，
       避免同一批字段在三处各写一遍、改一处漏两处。改动以新对象回抛（v-model），不直接改宿主对象。 -->
  <div class="grid grid-cols-1 gap-3" :class="channel === 'email' && 'sm:grid-cols-2'">
    <div v-for="f in fields" :key="f.key" :class="f.wide && 'sm:col-span-2'">
      <label class="mb-1.5 block text-xs text-ink-muted">{{ f.label }}</label>
      <input
        :type="f.type"
        :value="modelValue[f.key] || ''"
        :placeholder="f.placeholder"
        autocomplete="off"
        class="w-full rounded-xl border border-ink/10 bg-elevated px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
        @input="setField(f.key, $event.target.value)"
      />
      <p v-if="f.hint" class="mt-1 text-xs text-ink-muted">{{ f.hint }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  channel: { type: String, required: true },
  // 字段袋：组件按通道取用自己那几个键，改动以新对象回抛，由宿主 v-model 接住
  modelValue: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['update:modelValue'])

function setField(key, value) {
  emit('update:modelValue', { ...(props.modelValue || {}), [key]: value })
}

// 与后端 pools_schema._CRED_REQUIRED_FIELDS 一一对应，改字段时两边一起改
const FIELDS = {
  serverchan: [
    { key: 'serverchanKey', label: 'SendKey', placeholder: 'Server酱 SendKey' }
  ],
  pushplus: [
    { key: 'pushplusToken', label: 'Token', placeholder: 'PushPlus Token' }
  ],
  'pushplus-open': [
    { key: 'token', label: 'Token', placeholder: 'PushPlus 开放接口 Token（消息 token）', type: 'password',
      hint: '群推送专用：把合并签到结果发到 QQ 群；填消息 token，长期有效、无需刷新' }
  ],
  email: [
    { key: 'emailSmtp', label: 'SMTP 地址', placeholder: '如 smtp.qq.com' },
    { key: 'emailFrom', label: '发件人', placeholder: '登录 SMTP 的邮箱地址' },
    { key: 'emailPass', label: '授权码', placeholder: '邮箱授权码', type: 'password' },
    {
      key: 'emailTo', label: '默认收件人', placeholder: '多个用逗号分隔', wide: true,
      hint: '账号没单独指定收件人时，签到结果发到这里'
    }
  ]
}

const fields = computed(() => FIELDS[props.channel] || [])
</script>
