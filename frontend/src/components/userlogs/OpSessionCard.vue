<template>
  <!-- 会话卡：一段「登录 → 登出」的完整轨迹。
       卡内的竖轴只连接**本段会话内部**的事件——出了卡片就断。
       早前把轴画在整张列表上是错的：同一操作者反复出现的那些点被连成一条长线，
       视觉上像在暗示「这些账号之间有关联」，而它们唯一的共同点只是都发生过操作。 -->
  <article class="dash-card p-3.5">
    <!-- items-baseline：卡头混排 14px 用户名 / 11px 角色徽标 / 12px 时间跨度与时长，
         按盒居中会让各段文字基线错开（实测底边极差 2.25px），按基线对齐后降到 1px
         （剩余 1px 是 11px 与 14px 下伸部差异，基线本身已重合，属正确表现） -->
    <header class="flex flex-wrap items-baseline gap-x-2 gap-y-1">
      <span class="text-sm font-medium text-ink">{{ session.username || '系统' }}</span>
      <span class="rounded-md border border-ink/10 px-1.5 py-0.5 text-[11px] text-ink-muted">
        {{ opRoleLabel(session.role) }}
      </span>
      <span class="font-mono text-xs tabular-nums text-ink-muted">{{ span }}</span>
      <span class="text-xs text-ink-muted">· {{ duration }}</span>
      <span
        class="ml-auto shrink-0 rounded-full px-2 py-0.5 text-[11px]"
        :class="closeMeta.cls"
      >
        {{ closeMeta.label }}
      </span>
    </header>

    <ol ref="listRef" class="mt-2.5">
      <li
        v-for="(e, i) in visibleEvents"
        :key="e.id"
        class="flex items-start gap-2.5"
        :class="i === visibleEvents.length - 1 ? '' : 'pb-2.5'"
        :data-fresh="i >= PREVIEW_COUNT ? '' : null"
      >
        <!-- 轴列：自撑满行高，圆点上下各接半段，首条只向下、末条只向上；
             圆点套 ring-card 让线在圆点处断开，读起来是一串事件而不是一条连续线 -->
        <span class="relative flex w-1.5 shrink-0 justify-center self-stretch" aria-hidden="true">
          <span v-if="i > 0" class="absolute top-0 h-[10px] w-px bg-ink/10" />
          <span
            v-if="i < visibleEvents.length - 1"
            class="absolute bottom-0 top-[10px] w-px bg-ink/10"
          />
          <span
            class="relative z-10 mt-[7px] h-1.5 w-1.5 rounded-full ring-2 ring-card"
            :class="opCategoryMeta(e.category).dot"
          />
        </span>
        <!-- ⚠️ 时刻**不能**用 font-mono：等宽字体与正文（Segoe UI）的字形盒高度差一节，
             同一个 line-height 下基线必然错开 1–2px，看起来就是「时间与文字底部不齐」——
             实测 font-mono 盒高 14px、正文 17px，底边差 -1px；去掉 mono 改 tabular-nums 后底边差 0，
             且实测「15:00」与「18:38」宽度都是 28.48px，数字依旧等宽。
             同理不要用 pt-* 手工补偿：那是拿行高差做像素级凑数，字号一改就废。 -->
        <time
          class="w-10 shrink-0 whitespace-nowrap text-xs leading-5 tabular-nums text-ink-muted"
        >
          {{ e.time }}
        </time>
        <p class="min-w-0 flex-1 text-[13px] leading-5 text-ink">{{ opEventText(e) }}</p>
        <span class="shrink-0 text-xs leading-5 text-ink-muted">
          {{ opCategoryMeta(e.category).label }}
        </span>
      </li>
    </ol>

    <!-- 展开出口的塌陷与列表的增长同属一次操作，两边节奏要对上：
         按钮若凭空消失、列表却还在长，卡片的底边会连着跳两次 -->
    <Transition :css="false" @enter="onMoreEnter" @leave="onMoreLeave">
      <button
        v-if="hiddenCount > 0"
        type="button"
        class="mt-2 w-full rounded-lg py-1 text-xs font-medium text-brand transition hover:bg-brand/5"
        @click="expandAll"
      >
        展开其余 {{ hiddenCount }} 项操作
      </button>
    </Transition>
  </article>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { gsap } from 'gsap'
import { useCollapseTransition } from '@/composables/useCollapseTransition'
import {
  opCategoryMeta,
  opCloseMeta,
  opDurationText,
  opEventText,
  opRoleLabel,
  opSessionSpan,
} from '@/utils/opLogMeta'

const props = defineProps({
  session: { type: Object, required: true },
})

// 长会话折叠：一段会话可能有几十项操作，全铺开会把列表撑得没法扫。
// 只留前 5 项 + 一个展开出口，需要时再铺开。
const PREVIEW_COUNT = 5

const expanded = ref(false)
const hiddenCount = computed(() =>
  expanded.value ? 0 : Math.max(0, (props.session.events || []).length - PREVIEW_COUNT)
)
const visibleEvents = computed(() => {
  const all = props.session.events || []
  return expanded.value ? all : all.slice(0, PREVIEW_COUNT)
})

const span = computed(() => opSessionSpan(props.session))
const duration = computed(() =>
  opDurationText(props.session.durationSeconds, props.session.running)
)
const closeMeta = computed(() => opCloseMeta(props.session.closeReason))

const listRef = ref(null)
const reduceMotion = ref(false)
let mm = null

// 展开出口自身的塌陷补间（pad 与按钮的 py-1 对齐）
const { onEnter: onMoreEnter, onLeave: onMoreLeave } = useCollapseTransition(
  () => reduceMotion.value,
  { pad: 4, duration: 0.22 }
)

// 展开其余操作：列表高度从旧值补间到新值，新出现的行错峰淡入。
// 这里不用 useCollapseTransition——那个面向「元素挂载/卸载」的折叠，
// 而本处容器一直都在、只是内容变多，所以前后各量一次高度自己补间。
// 光补间高度不淡入新行，行会随容器「瞬间长出来」，看着像卡了一下。
async function expandAll() {
  const el = listRef.value
  if (expanded.value || !el) return
  if (reduceMotion.value) {
    expanded.value = true
    return
  }
  const from = el.getBoundingClientRect().height
  expanded.value = true
  await nextTick()
  const to = el.getBoundingClientRect().height
  gsap.fromTo(
    el,
    { height: from, overflow: 'hidden' },
    {
      height: to,
      duration: 0.3,
      ease: 'power2.out',
      onComplete: () => gsap.set(el, { clearProps: 'height,overflow' }),
    }
  )
  gsap.fromTo(
    el.querySelectorAll('li[data-fresh]'),
    { autoAlpha: 0, y: 6 },
    {
      autoAlpha: 1,
      y: 0,
      duration: 0.26,
      stagger: 0.045,
      delay: 0.06,
      ease: 'power2.out',
      clearProps: 'opacity,transform',
    }
  )
}

onMounted(() => {
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
  gsap.killTweensOf(listRef.value || [])
})
</script>
