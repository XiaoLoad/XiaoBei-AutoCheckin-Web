<template>
  <!-- 流水行：平铺列表里的一格。这里**不画任何贯穿竖线**——
       一行与下一行之间没有关系，只有先后顺序；线一旦画上就会被读成关联。
       左侧等宽时间 + 分类色点，右侧主文案，第二行才是操作者与来源。 -->
  <li
    class="cursor-pointer py-2.5 transition-colors"
    :class="open ? 'bg-brand/[0.025]' : 'hover:bg-ink/[0.02]'"
    @click="emit('toggle', row)"
  >
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

        <!-- 展开区：一块下沉面板。边界靠内描边交代，而不是用更浅的底色去糊——
             两块近白叠在一起，读者分不出哪层是哪层。
             分区用「眉标 + 细线」而非段落堆叠：审计详情是份小单据，标题栏比空行更好扫。
             ⚠️纵向 padding 必须留在类上（动画收尾 clearProps 要交还给它），
             且值须与 useCollapseTransition 的 pad 一致，否则展开完成会贴边。 -->
        <Transition :css="false" @enter="onDetailEnter" @leave="onDetailLeave">
          <div
            v-if="open"
            class="mt-2.5 ml-4 rounded-xl bg-cloud/50 px-3.5 py-3.5 ring-1 ring-inset ring-ink/[0.06]"
            @click.stop
          >
            <!-- 失败原因前置：失败行最该被看见的就是原因，
                 混在键值表里跟「操作账号」平起平坐等于没说 -->
            <div
              v-if="failReason"
              data-detail-item
              class="mb-3 flex items-start gap-2 rounded-lg bg-danger/[0.07] px-2.5 py-2"
            >
              <Icon name="alert" :size="13" class="mt-0.5 shrink-0 text-danger" />
              <div class="min-w-0">
                <p class="text-[11px] font-medium text-danger">失败原因</p>
                <p class="mt-0.5 break-words text-xs leading-5 text-ink">{{ failReason }}</p>
              </div>
            </div>

            <!-- 变更：审计真正要看的东西，也是整块展开区里视觉最重的一行 -->
            <section v-if="changes.length" data-detail-item>
              <header class="flex items-center gap-2">
                <span class="shrink-0 text-[11px] font-medium tracking-wide text-ink-muted">
                  变更
                </span>
                <span class="h-px flex-1 bg-ink/[0.07]" aria-hidden="true" />
              </header>
              <ul class="mt-1.5 flex flex-col gap-y-1.5">
                <li
                  v-for="c in changes"
                  :key="c.field"
                  class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs"
                >
                  <span class="w-16 shrink-0 text-[11px] text-ink-muted">
                    {{ opFieldLabel(c.field) }}
                  </span>
                  <!-- 旧值退后（中性底），新值上前（品牌底 + 加粗）：
                       一眼分得出哪头是改之前、哪头是改之后，不必逐字去读 -->
                  <span class="rounded-md bg-ink/[0.05] px-2 py-0.5 tabular-nums text-ink-muted">
                    {{ opFieldValue(c.field, c.from) }}
                  </span>
                  <!-- 迁移箭头用「短横 + 尖」而不是一段普通箭头字体或等号：
                       它要说的是值从这头挪到了那头，方向本身就是信息 -->
                  <span class="flex items-center text-brand/50" aria-hidden="true">
                    <span class="h-px w-2.5 bg-current" />
                    <Icon name="chevron-right" :size="12" class="-ml-px" />
                  </span>
                  <span
                    class="rounded-md bg-brand/10 px-2 py-0.5 font-medium tabular-nums text-brand ring-1 ring-inset ring-brand/10"
                  >
                    {{ opFieldValue(c.field, c.to) }}
                  </span>
                </li>
              </ul>
            </section>

            <!-- 上下文：这次操作发生在什么环境里（谁、对谁、从哪来）。
                 降级成键值网格即可；UA 允许折行——它常是排查客户端的唯一线索，截断就废了 -->
            <section v-if="extras.length" class="mt-3" data-detail-item>
              <header class="flex items-center gap-2">
                <span class="shrink-0 text-[11px] font-medium tracking-wide text-ink-muted">
                  上下文
                </span>
                <span class="h-px flex-1 bg-ink/[0.07]" aria-hidden="true" />
              </header>
              <dl class="mt-1.5 grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
                <div v-for="it in extras" :key="it.label" class="flex min-w-0 gap-2">
                  <dt class="w-16 shrink-0 text-[11px] leading-5 text-ink-muted">{{ it.label }}</dt>
                  <dd class="min-w-0 break-words text-xs leading-5 text-ink-soft">{{ it.value }}</dd>
                </div>
              </dl>
            </section>

            <p
              v-if="!failReason && !changes.length && !extras.length"
              data-detail-item
              class="text-xs text-ink-muted"
            >
              本次操作没有字段变更，也没有其它记录项。
            </p>
          </div>
        </Transition>
      </div>
    </div>
  </li>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'
import { useCollapseTransition } from '@/composables/useCollapseTransition'
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

// 展开/收起走统一的高度补间（列表详情与「正在进行」卡片共用同一实现）。
// pad 必须等于面板类上的 py-3.5（14px），否则动画收尾 clearProps 会把内边距交还给 0。
const reduceMotion = ref(false)
let mm = null
const { onEnter: onDetailEnter, onLeave: onDetailLeave } = useCollapseTransition(
  () => reduceMotion.value,
  { pad: 14 }
)

const fail = computed(() => props.row.result === 'fail')
const categoryMeta = computed(() => opCategoryMeta(props.row.category))
const timeText = computed(() => (props.row.createdAt || '').slice(11, 19) || '—')

const changes = computed(() => {
  const list = props.row.detail && props.row.detail.changes
  return Array.isArray(list) ? list : []
})

// 后端只在登录失败行写 detail.reason（见 services/op_log.py 的登录失败订阅），
// 因此它不参与下面的键值表，而是独占最上面那块
const failReason = computed(() => {
  const d = props.row.detail
  return d && d.reason ? String(d.reason) : ''
})

// 明细里除 changes / reason 之外的字段：按固定顺序与中文标签罗列，未知键直接跳过
// （后端 detail 只写这几个键，出现新键说明契约变了，宁可先不显示也不要撑乱版面）
const EXTRA_LABELS = [
  ['account', '操作账号'],
  ['targetUsername', '目标用户'],
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

onMounted(() => {
  // 与列表详情同款：命中「减少动态效果」时展开/收起直接落终态
  mm = gsap.matchMedia()
  mm.add('(prefers-reduced-motion: reduce)', () => {
    reduceMotion.value = true
    return () => {
      reduceMotion.value = false
    }
  })
})

onUnmounted(() => {
  mm?.revert()
})
</script>
