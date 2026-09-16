<template>
  <!-- 流水行：平铺列表里的一格。这里**不画任何贯穿竖线**——
       一行与下一行之间没有关系，只有先后顺序；线一旦画上就会被读成关联。
       左侧等宽时间 + 分类色点，右侧主文案，第二行才是操作者与来源。 -->
  <li class="cursor-pointer py-2.5" @click="emit('toggle', row)">
    <div class="flex items-start gap-2.5">
      <!-- ⚠️ 时刻同样不用 font-mono：与正文的字形盒高度不同会让基线错开约 1px
           （原因与实测数据见 OpSessionCard.vue 同处注释），tabular-nums 已保证数字等宽 -->
      <time
        class="w-16 shrink-0 whitespace-nowrap text-xs leading-5 tabular-nums text-ink-muted"
      >
        {{ timeText }}
      </time>
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2.5">
          <!-- 失败行直接把色点换成危险色：列表里最需要被一眼捞出来的就是它 -->
          <span
            class="h-1.5 w-1.5 shrink-0 rounded-full"
            :class="fail ? 'bg-danger' : categoryMeta.dot"
          />
          <p class="min-w-0 flex-1 truncate text-[13px] leading-5 text-ink">{{ opEventText(row) }}</p>
          <span class="shrink-0 text-xs leading-5 text-ink-muted">{{ categoryMeta.label }}</span>
          <Icon
            name="chevron-down"
            :size="14"
            class="shrink-0 text-ink/25 transition-transform duration-200"
            :class="open ? 'rotate-180' : ''"
          />
        </div>

        <!-- 与首行文案左对齐：色点 6px + gap 10px -->
        <p class="mt-1 flex flex-wrap items-center gap-x-1.5 pl-4 text-[11px] text-ink-muted">
          <span>{{ row.username || '系统' }}</span>
          <span class="text-ink/20">·</span>
          <span>{{ opRoleLabel(row.role) }}</span>
          <template v-if="row.ip">
            <span class="text-ink/20">·</span>
            <span class="tabular-nums">{{ row.ip }}</span>
          </template>
          <span
            v-if="fail"
            class="rounded-full bg-danger/10 px-1.5 py-0.5 font-medium text-danger"
          >
            失败
          </span>
        </p>

        <!-- 展开区：变更明细优先（审计真正要看的 from→to），其余字段按标签表罗列 -->
        <div
          v-if="open"
          class="mt-2.5 ml-4 rounded-xl border border-ink/5 bg-cloud/60 p-3"
          @click.stop
        >
          <template v-if="changes.length">
            <p class="mb-1.5 text-[11px] font-medium text-ink-muted">变更明细</p>
            <ul class="flex flex-col gap-1.5">
              <li
                v-for="c in changes"
                :key="c.field"
                class="flex flex-wrap items-center gap-2 text-xs"
              >
                <span class="w-14 shrink-0 text-ink-muted">{{ opFieldLabel(c.field) }}</span>
                <span class="rounded-md bg-white px-1.5 py-0.5 text-ink-soft ring-1 ring-ink/5">
                  {{ opFieldValue(c.field, c.from) }}
                </span>
                <Icon name="chevron-right" :size="12" class="text-ink/25" />
                <span class="rounded-md bg-brand/10 px-1.5 py-0.5 font-medium text-brand">
                  {{ opFieldValue(c.field, c.to) }}
                </span>
              </li>
            </ul>
          </template>

          <dl class="mt-2 grid grid-cols-1 gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
            <div v-for="it in extras" :key="it.label" class="flex min-w-0 gap-2">
              <dt class="shrink-0 text-ink-muted">{{ it.label }}</dt>
              <dd class="min-w-0 truncate text-ink-soft" :title="it.value">{{ it.value }}</dd>
            </div>
          </dl>
          <p v-if="!changes.length && !extras.length" class="text-xs text-ink-muted">
            本次操作没有可展开的明细。
          </p>
        </div>
      </div>
    </div>
  </li>
</template>

<script setup>
import { computed } from 'vue'
import Icon from '@/components/Icon.vue'
import {
  opCategoryMeta,
  opEventText,
  opFieldLabel,
  opFieldValue,
  opRoleLabel,
} from '@/utils/opLogMeta'

const props = defineProps({
  row: { type: Object, required: true },
  open: { type: Boolean, default: false },
})
const emit = defineEmits(['toggle'])

const fail = computed(() => props.row.result === 'fail')
const categoryMeta = computed(() => opCategoryMeta(props.row.category))
const timeText = computed(() => (props.row.createdAt || '').slice(11, 19) || '—')

const changes = computed(() => {
  const list = props.row.detail && props.row.detail.changes
  return Array.isArray(list) ? list : []
})

// 明细里除 changes 之外的字段：按固定顺序与中文标签罗列，未知键直接跳过
// （后端 detail 只写这几个键，出现新键说明契约变了，宁可先不显示也不要撑乱版面）
const EXTRA_LABELS = [
  ['account', '操作账号'],
  ['targetUsername', '目标用户'],
  ['reason', '失败原因'],
  ['passwordChanged', '同时改了密码'],
  ['stub', '实现状态'],
  ['role', '新建角色'],
  ['enabled', '初始状态'],
  ['quota', '初始额度'],
]

function fmt(label, raw) {
  if (typeof raw === 'boolean') {
    if (label === '实现状态') return raw ? '桩接口，未实际销毁' : '已落地'
    return raw ? '是' : '否'
  }
  return String(raw)
}

const extras = computed(() => {
  const d = props.row.detail
  if (!d || typeof d !== 'object') return []
  const out = []
  for (const [key, label] of EXTRA_LABELS) {
    if (key === 'targetUsername' && !d[key]) continue
    if (d[key] === undefined || d[key] === null || d[key] === '') continue
    out.push({ label, value: fmt(label, d[key]) })
  }
  if (props.row.userAgent) out.push({ label: '客户端', value: props.row.userAgent })
  return out
})
</script>
