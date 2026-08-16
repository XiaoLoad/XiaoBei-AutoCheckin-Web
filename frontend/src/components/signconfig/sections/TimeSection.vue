<template>
  <ConfigSection title="时间配置" icon="clock" :source="source" :error="error" :required="required">
    <div class="space-y-4">
      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-muted">每日签到时间段</label>
        <div class="flex items-center gap-2">
          <BaseSelect v-model="config.time.startHour" :options="hourOptions" size="sm" class="w-24" />
          <span class="text-sm text-ink-muted">至</span>
          <BaseSelect v-model="config.time.endHour" :options="hourOptions" size="sm" class="w-24" />
          <span class="text-sm text-ink-muted">时</span>
        </div>
      </div>
      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-muted">随机延时上限</label>
        <div class="flex items-center gap-2">
          <input
            v-model.number="config.time.randomDelayMax"
            type="number"
            min="0"
            class="w-28 rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
          />
          <span class="text-sm text-ink-muted">分钟</span>
        </div>
        <p class="mt-1.5 text-xs text-ink-muted">系统在时限内随机延迟秒数，避免并发触发</p>
      </div>

      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-muted">触发星期（可多选）</label>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="d in weekDays"
            :key="d.value"
            type="button"
            class="rounded-lg border px-3 py-1.5 text-sm transition"
            :class="config.time.weekdays.includes(d.value) ? 'border-brand bg-brand/10 text-brand' : 'border-ink/10 text-ink-soft hover:bg-cloud'"
            @click="toggleWeekday(d.value)"
          >
            {{ d.label }}
          </button>
        </div>
      </div>

      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-muted">签到模式</label>
        <div class="inline-flex rounded-xl bg-cloud p-1">
          <button
            v-for="m in modes"
            :key="m.value"
            type="button"
            class="rounded-lg px-3 py-1.5 text-sm font-medium transition"
            :class="config.time.mode === m.value ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
            @click="config.time.mode = m.value"
          >
            {{ m.label }}
          </button>
        </div>
        <p v-if="config.time.mode === 'holiday'" class="mt-2 rounded-lg bg-info/10 px-3 py-2 text-xs text-info">
          节假日模式：法定节假日跳过、工作日执行。运行时按年调用第三方节假日接口（如 api.apisbo.com/holidays）自动适配校历，无需管理员维护。
        </p>
      </div>
    </div>
  </ConfigSection>
</template>

<script setup>
import { computed } from 'vue'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import BaseSelect from '@/components/BaseSelect.vue'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' },
  error: { type: String, default: '' },
  required: { type: Boolean, default: false }
})

const hourOptions = computed(() => Array.from({ length: 24 }, (_, h) => ({ label: String(h), value: h })))
const weekDays = [
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
  { value: 7, label: '周日' }
]
const modes = [
  { value: 'normal', label: '普通模式' },
  { value: 'holiday', label: '节假日模式' }
]

function toggleWeekday(v) {
  const i = props.config.time.weekdays.indexOf(v)
  if (i === -1) props.config.time.weekdays.push(v)
  else if (props.config.time.weekdays.length > 1) props.config.time.weekdays.splice(i, 1)
}
</script>
