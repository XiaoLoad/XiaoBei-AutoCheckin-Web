<template>
  <ConfigSection title="高级设置" icon="settings" :source="source">
    <div class="space-y-3">
      <!-- 模式开关：机型池分配 / 自定义 UA 二选一 -->
      <div>
        <label class="mb-1 block text-xs font-medium text-ink-muted">请求 UA（设备身份）</label>
        <div class="flex gap-1.5">
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs font-medium transition"
            :class="poolMode
              ? 'bg-brand text-white shadow-sm shadow-brand/25'
              : 'bg-cloud/70 text-ink-soft hover:bg-cloud hover:text-ink'"
            @click="config.advanced.uaPoolEnabled = true"
          >机型池分配</button>
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs font-medium transition"
            :class="!poolMode
              ? 'bg-brand text-white shadow-sm shadow-brand/25'
              : 'bg-cloud/70 text-ink-soft hover:bg-cloud hover:text-ink'"
            @click="config.advanced.uaPoolEnabled = false"
          >自定义 UA</button>
        </div>
      </div>

      <!-- 机型池分配：说明池语义与参与条件，附启用机型概览 -->
      <div v-if="poolMode" class="space-y-1.5">
        <p class="text-[11px] leading-relaxed text-ink-muted">
          执行时按账号从「资源池 → UA 模板」中<b class="text-ink-soft">启用中</b>的机型确定性分配：
          同一账号固定同一机型（设备身份不漂移），不同账号散开到不同机型，避免多个账号呈现同一设备。
        </p>
        <div class="rounded-lg bg-cloud/60 px-3 py-2 text-xs">
          <template v-if="enabledCount">
            <span class="font-medium text-ink">当前 {{ enabledCount }} 台机型参与分配</span>
            <!-- 机型多时只列前几个 + 省略，500 台全列会把卡片撑爆 -->
            <span v-if="enabledCount <= 8" class="ml-1.5 text-ink-muted">{{ enabledNames }}</span>
            <span v-else class="ml-1.5 text-ink-muted">{{ enabledHead }} 等 {{ enabledCount }} 台</span>
          </template>
          <template v-else>
            <span class="text-amber">机型池为空：请先到「资源池 → UA 模板」添加并启用机型，否则执行时回退平台默认 UA</span>
          </template>
        </div>
      </div>

      <!-- 自定义 UA：全员统一，显式覆盖；可从机型池选一条作为底稿 -->
      <div v-else class="space-y-2">
        <div>
          <label class="mb-1 block text-xs font-medium text-ink-muted">从机型池选一条（可搜索）</label>
          <BaseSelect
            v-model="pickedTemplateId"
            :options="allUaOptions"
            :searchable="true"
            placeholder="选择机型模板填入下方，或直接粘贴"
            size="sm"
            class="w-72"
          />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-ink-muted">自定义 UA</label>
          <textarea
            v-model="config.advanced.customUa"
            rows="2"
            class="w-full rounded-xl border border-ink/10 bg-elevated px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
            placeholder="粘贴自定义 User-Agent 字符串（所有账号统一使用该 UA）"
          />
        </div>
        <p class="text-[11px] text-ink-muted">
          所有账号统一使用该 UA；留空则回退平台默认 UA。下拉只是把池内模板填进来作为底稿，
          之后的增删改不会同步——机型池随账号分配请用上方「机型池分配」模式。
        </p>
      </div>
    </div>
  </ConfigSection>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import { useSignConfigStore } from '@/stores/signConfig'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' }
})

const store = useSignConfigStore()
const poolMode = computed(() => !!props.config.advanced.uaPoolEnabled)
const enabledTemplates = computed(() => store.uaTemplates.filter((u) => u.enabled !== false))
const enabledCount = computed(() => enabledTemplates.value.length)
const enabledNames = computed(() => enabledTemplates.value.map((u) => u.name || '未命名').join(' / '))
const enabledHead = computed(() =>
  enabledTemplates.value.slice(0, 8).map((u) => u.name || '未命名').join(' / '))

// 自定义模式下的模板快选：选中即把 UA 字符串填进 customUa 作为底稿（单向快照，不保持引用）
const allUaOptions = computed(() =>
  store.uaTemplates.map((u) => ({ label: u.name || u.ua.slice(0, 32), value: u.id })))
const pickedTemplateId = ref('')
watch(pickedTemplateId, (id) => {
  if (!id) return
  const t = store.uaTemplates.find((u) => u.id === id)
  if (t?.ua) props.config.advanced.customUa = t.ua
  pickedTemplateId.value = '' // 一次性动作：填完即复位，允许再次选择同一条
})
</script>
