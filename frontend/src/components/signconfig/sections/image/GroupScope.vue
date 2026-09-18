<template>
  <div class="space-y-2.5">
    <!-- 分组类型：与取图方式同为互斥二选一，沿用分段控件而非下拉 -->
    <div class="flex items-center gap-2">
      <span class="flex-none text-xs text-ink-muted">按</span>
      <div class="inline-flex rounded-lg bg-cloud p-0.5" role="group" aria-label="按哪类分组取图">
        <button
          v-for="k in kindOptions"
          :key="k.value"
          type="button"
          class="rounded-md px-2.5 py-1 text-xs font-medium transition"
          :class="config.groupKind === k.value ? 'bg-elevated text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
          :aria-pressed="config.groupKind === k.value"
          @click="config.groupKind = k.value"
        >
          {{ k.label }}
        </button>
      </div>
      <span class="flex-none text-xs text-ink-muted">取图</span>
    </div>

    <!-- 健康度与兜底行只属于配置套：那时「多少个分组/账号」是待办清单。
         账号任务配置里同一组数字会被读成「这个账号的处境」，故该语境下整块收起；
         该账号的实际结果由 ResolvedScope 给，真漏网时其下方才补一行就地兜底。 -->
    <template v-if="!isAccountView">
      <!-- 有漏网：兜底行就地浮出。分组归属与图库归属都可能缺，两者去处相同，合并成一行 -->
      <div v-if="hasGap" class="rounded-xl border border-dashed border-ink/15 bg-cloud/40 px-3 py-2.5">
        <p class="text-xs leading-relaxed text-warning">{{ gapText }}</p>
        <div class="mt-2 flex items-center gap-2">
          <span class="flex-none text-xs text-ink-muted">兜底</span>
          <div class="min-w-0 flex-1">
            <LibraryPicker
              v-model="config.groupId"
              tone="fallback"
              :options="groupOptions"
              :images="fallbackImages"
            />
          </div>
        </div>
      </div>

      <!-- 没有漏网：一句健康度，兜底收成细链接（需要时再展开，卡面保持干净） -->
      <template v-else>
        <div class="flex items-center gap-2">
          <p class="min-w-0 flex-1 text-xs text-ink-muted">{{ healthText }}</p>
          <button
            v-if="!showFallback"
            type="button"
            class="flex-none text-xs font-medium text-brand transition hover:underline"
            @click="showFallback = true"
          >
            设置兜底图库（可选）
          </button>
        </div>
        <div v-if="showFallback" class="flex items-center gap-2 xb-block-in">
          <span class="flex-none text-xs text-ink-muted">兜底</span>
          <div class="min-w-0 flex-1">
            <LibraryPicker
              v-model="config.groupId"
              tone="fallback"
              :options="groupOptions"
              :images="fallbackImages"
            />
          </div>
        </div>
      </template>
    </template>

    <p v-if="!isAdmin" class="text-xs text-ink-muted">
      分组与图库的对应关系在「分组」页维护。
      <button type="button" class="font-medium text-brand transition hover:underline" @click="$emit('bind')">
        去设置
      </button>
    </p>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import LibraryPicker from '@/components/signconfig/sections/image/LibraryPicker.vue'

const props = defineProps({
  // 直接改写（配置草稿编辑模式，与其他 section 一致）
  config: { type: Object, required: true },
  // { total, unboundGroups, unboundAccounts }；null = 尚未核对完成或管理员无分组
  audit: { type: Object, default: null },
  // 账号上下文：传入即账号视角，收起健康度统计与兜底行
  account: { type: Object, default: null },
  groupOptions: { type: Array, default: () => [] },
  fallbackImages: { type: Array, default: () => [] },
  isAdmin: { type: Boolean, default: false }
})

defineEmits(['bind'])

const kindOptions = [
  { label: '寝室分组', value: 'dorm' },
  { label: '班级分组', value: 'class' }
]

const isAccountView = computed(() => !!props.account)
const kindLabel = computed(() => (props.config.groupKind === 'class' ? '班级分组' : '寝室分组'))
// 已配过兜底就默认展开，否则收成细链接，避免「无漏网时凭空多一个选择器」
const showFallback = ref(!!props.config.groupId)

// 漏网 = 分组没绑图库（这些分组下的账号取不到图）+ 账号没有归属分组。
// 两者去处相同（同一个兜底图库），故合并成一句，不拆两行。
const hasGap = computed(() => {
  const a = props.audit
  return !!a && (a.unboundGroups > 0 || a.unboundAccounts > 0)
})

const gapText = computed(() => {
  const a = props.audit
  const parts = []
  if (a.unboundGroups) parts.push(`${a.unboundGroups} 个${kindLabel.value}未绑图库`)
  if (a.unboundAccounts) parts.push(`${a.unboundAccounts} 个账号未分组`)
  return `${parts.join('、')}，这些账号会走兜底图库`
})

const healthText = computed(() => {
  const a = props.audit
  if (!a) return `图库归属在「分组」页设置`
  if (a.total === 0) return '暂无启用账号'
  return `${a.total} 个${kindLabel.value}都已绑定图库，账号均有归属`
})

// 与 script setup 末尾约定一致：watch 写在最后，避免 setup 阶段 TDZ。
// 切换配置套时组件不重建，已配兜底的套必须把兜底行展开，否则会被读成「没配兜底」。
watch(() => props.config.groupId, (v) => {
  if (v) showFallback.value = true
})
</script>
