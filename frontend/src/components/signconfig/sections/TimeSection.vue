<template>
  <ConfigSection title="时间配置" icon="clock" :source="source" :error="error" :required="required">
    <div class="space-y-4">
      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-muted">每日签到时间段</label>
        <div class="flex items-center gap-2">
          <!-- w-full 会让下拉框撑满整行挤压相邻文字，故用固定宽度的 shrink-0 容器包裹 -->
          <div class="w-24 shrink-0">
            <BaseSelect v-model="config.time.startHour" :options="hourOptions" size="sm" editable numeric />
          </div>
          <span class="text-sm text-ink-muted">至</span>
          <div class="w-24 shrink-0">
            <BaseSelect v-model="config.time.endHour" :options="hourOptions" size="sm" editable numeric />
          </div>
          <span class="text-sm text-ink-muted">时</span>
        </div>
        <p class="mt-1.5 text-xs text-ink-muted">部分签到任务仅允许在此时段内签到，属于业务限制，与下方「定时签到时间」相互独立。可下拉选择或直接键入数字。</p>
      </div>

      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-muted">定时签到时间</label>
        <div class="flex items-center gap-2">
          <div class="w-20 shrink-0">
            <BaseSelect v-model="config.time.signTime.hour" :options="hourOptions" size="sm" editable numeric />
          </div>
          <span class="text-sm text-ink-muted">时</span>
          <div class="w-20 shrink-0">
            <BaseSelect v-model="config.time.signTime.minute" :options="minuteOptions" size="sm" editable numeric />
          </div>
          <span class="text-sm text-ink-muted">分</span>
        </div>
        <p class="mt-1.5 text-xs text-ink-muted">调度器在每周选定星期、该时刻附近（叠加随机延时）自动触发；定时任务页默认采纳此时间。可下拉选择或直接键入数字。</p>
      </div>

      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-muted">随机延时上限</label>
        <div class="flex items-center gap-2">
          <input
            v-model.number="config.time.randomDelayMax"
            type="number"
            min="0"
            class="w-28 rounded-xl border border-ink/10 bg-elevated px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
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
            :class="config.time.mode === m.value ? 'bg-elevated text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
            @click="config.time.mode = m.value"
          >
            {{ m.label }}
          </button>
        </div>
        <p v-if="config.time.mode === 'holiday'" class="mt-2 rounded-lg bg-info/10 px-3 py-2 text-xs text-info">
          节假日模式：触发星期、签到时刻等设置照常生效，执行时遇到法定节假日（元旦/春节/清明/劳动/端午/中秋/国庆）自动跳过并记录。双休日不算节假日、照常执行；调休补班日照常执行。
        </p>
        <div v-if="config.time.mode === 'holiday'" class="mt-2">
          <BaseCheckbox v-model="config.time.holiday.lastDaySign" label="假期末日照常签到" />
          <p class="mt-1 text-xs text-ink-muted">学校常在法定假期最后一天查寝签到，开启后假期末日在触发星期内则照常执行；默认关闭（末日也跳过）。</p>
        </div>
      </div>
    </div>
  </ConfigSection>
</template>

<script setup>
import { computed } from 'vue'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import BaseCheckbox from '@/components/BaseCheckbox.vue'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' },
  error: { type: String, default: '' },
  required: { type: Boolean, default: false }
})

// 小时下拉补零显示（01/02…23），与定时任务页 pad() 展示保持一致，提升观感
const hourOptions = computed(() =>
  Array.from({ length: 24 }, (_, h) => ({ label: String(h).padStart(2, '0'), value: h }))
)
// 分钟下拉同样补零（00/01…59），与小时保持一致
const minuteOptions = computed(() =>
  Array.from({ length: 60 }, (_, m) => ({ label: String(m).padStart(2, '0'), value: m }))
)
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
