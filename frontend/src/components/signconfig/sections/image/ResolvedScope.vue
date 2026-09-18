<template>
  <!-- 账号视角：配置套不知道谁在用图，只显示规则；这里代入具体账号，显示结论，
       且只在真的漏网时说一句具体的话，不出现任何分组/账号计数。 -->
  <div v-if="resolved">
    <p class="mb-1.5 text-xs text-ink-muted">{{ accountName }} 实际会取到</p>
    <div
      class="flex items-center gap-2 rounded-xl px-3 py-2"
      :class="resolved.reason ? 'border border-dashed border-ink/15 bg-cloud/50' : 'bg-brand/5 ring-1 ring-inset ring-brand/15'"
    >
      <span class="flex min-w-0 flex-1 items-center gap-1.5">
        <span class="truncate text-xs text-ink-soft">{{ resolved.groupName || '未分组' }}</span>
        <Icon name="chevron-right" :size="12" class="flex-none text-ink-muted" />
        <span class="truncate text-xs font-medium" :class="resolved.reason ? 'text-ink-soft' : 'text-brand'">
          {{ resolved.imageName }}
        </span>
      </span>
      <span class="flex-none text-xs text-ink-muted">{{ resolved.count }} 张</span>
    </div>
    <p v-if="resolved.reason" class="mt-1.5 text-xs leading-relaxed text-warning">
      <template v-if="resolved.reason === 'unbound-group'">
        所在分组未绑定图库，{{ fallbackSuffix }}。
      </template>
      <template v-else> 该账号未加入任何{{ kindLabel }}，{{ fallbackSuffix }}。 </template>
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  // { groupName, imageName, count, reason: '' | 'unbound-group' | 'no-group', fallbackSet }
  // null = 不适用（固定图库模式，或核对尚未完成）
  resolved: { type: Object, default: null },
  accountName: { type: String, default: '' },
  groupKind: { type: String, default: 'dorm' }
})

const kindLabel = computed(() => (props.groupKind === 'class' ? '班级分组' : '寝室分组'))
// 没配兜底时后端会一路退到全部图库，不能对用户说「将使用兜底图库」
const fallbackSuffix = computed(() =>
  props.resolved?.fallbackSet ? '将使用兜底图库' : '也未设置兜底图库，将使用全部图库'
)
</script>
