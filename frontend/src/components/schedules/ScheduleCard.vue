<template>
  <article ref="root" class="sched-card dash-card relative flex flex-col overflow-hidden p-4 transition duration-300 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-ink/5" @click="$emit('open-config', schedule)">
    <!-- 左侧状态色条：开启时品牌蓝竖向铺满，GSAP 缩放呈现 -->
    <span
      ref="accent"
      class="pointer-events-none absolute left-0 top-0 h-full w-1 origin-top bg-brand"
      :class="schedule.enabled ? 'opacity-100' : 'opacity-0'"
    />

    <!-- 身份区：真实姓名为卡片主视觉（首字头像 + 放大字号），学院 / 专业 / 学号依次降级 -->
    <div class="flex items-start gap-2.5">
      <span class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand/10 text-[15px] font-semibold text-brand">
        <template v-if="displayName">{{ displayName.charAt(0) }}</template>
        <Icon v-else name="user" :size="16" />
      </span>

      <div class="min-w-0 flex-1">
        <!-- 姓名作主视觉：完整展示、可换行，不省略；任务类型徽标随行 -->
        <div class="flex items-start gap-2">
          <span class="break-words text-base font-semibold leading-tight text-ink line-clamp-2">{{ displayName }}</span>
          <span class="shrink-0 rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-medium text-brand">{{ schedule.taskLabel }}</span>
        </div>
        <!-- 学院 · 专业：单行省略，悬停由 title 看全文，不撑高卡片 -->
        <p v-if="orgText" class="mt-1 truncate text-xs text-ink-soft" :title="orgText">{{ orgText }}</p>
        <!-- 学号 · 班级 · 账号：单行省略，悬停看全文 -->
        <p v-if="idText" class="mt-0.5 truncate text-[11px] tabular-nums text-ink-muted" :title="idText">{{ idText }}</p>
      </div>

      <!-- 自定义开关（GSAP 驱动滑块） -->
      <button
        type="button"
        role="switch"
        :aria-checked="schedule.enabled"
        :disabled="!schedule.accountEnabled || noConfigSet || switching"
        class="relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition-colors disabled:cursor-not-allowed"
        :class="schedule.enabled ? 'bg-brand' : 'bg-ink/15'"
        @click.stop="$emit('toggle', schedule.id, !schedule.enabled)"
      >
        <span ref="knob" class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow" />
      </button>
    </div>

    <!-- 配置来源胶囊：真实配置套名（套用哪个显示哪个）/ 自定义 / 未关联 + 位置 -->
    <div class="mt-2.5 flex items-center gap-1.5 rounded-lg bg-cloud/70 px-2.5 py-1.5 text-[11px]">
      <Icon name="layers" :size="12" class="shrink-0 text-brand" />
      <span
        class="min-w-0 flex-1 truncate font-medium text-ink-soft"
        :title="`关联「${configMeta.presetSetName}」`"
      >{{ configMeta.presetSetName }}</span>
      <span
        v-if="configMeta.locationName && configMeta.locationName !== '未设置位置'"
        class="max-w-[45%] shrink-0 truncate text-ink-muted"
        :title="configMeta.locationName"
      >{{ configMeta.locationName }}</span>
    </div>

    <!-- 下一次执行：卡片最重要的运行时信息，品牌色高亮块 -->
    <div class="mt-2.5 rounded-xl border border-brand/15 bg-brand/5 px-3 py-2">
      <div class="flex items-center justify-between gap-2">
        <span class="text-[11px] text-ink-muted">下一次执行</span>
        <span class="text-[11px] font-medium" :class="statusCls">{{ statusText }}</span>
      </div>
      <p class="mt-0.5 truncate text-sm font-semibold text-brand" :title="nextRunText">{{ nextRunText }}</p>
    </div>

    <!-- 模式 chip + 上次运行 -->
    <div class="mt-2.5 flex items-center justify-between gap-2">
      <span class="inline-flex items-center gap-1 rounded-full bg-cloud px-2 py-0.5 text-[11px] text-ink-soft">
        <Icon name="clock" :size="12" />{{ modeText }}
      </span>
      <span class="truncate text-xs text-ink-muted">上次：{{ lastRunText }}</span>
    </div>

    <!-- 账号未启用提示 -->
    <p v-if="!schedule.accountEnabled" class="mt-1.5 text-[11px] text-warning">
      平台账号未启用，无法开启定时（请先在「账号管理」启用该账号）
    </p>

    <!-- 跟随配置套但未绑定配置套：无法开启 -->
    <p v-else-if="noConfigSet" class="mt-1.5 text-[11px] text-warning">
      未绑定配置套，无法开启（请先在「签到配置」绑定）
    </p>

    <!-- 操作：删除（带二次确认）；点击卡片其余区域即打开任务配置抽屉 -->
    <div class="mt-auto flex items-center justify-between gap-2 pt-2.5">
      <!-- 删除：常态显示入口，点击后切换为二次确认，避免误删 -->
      <div class="flex items-center gap-1">
        <button
          v-if="!confirming"
          type="button"
          class="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-sm font-medium text-danger/80 transition hover:bg-danger/10"
          @click.stop="confirming = true"
        >
          <Icon name="trash" :size="14" />删除
        </button>
        <template v-else>
          <button
            type="button"
            class="inline-flex h-8 items-center rounded-lg bg-danger px-2.5 text-sm font-medium text-white transition hover:bg-danger/90"
            @click.stop="confirmDelete"
          >
            确认删除
          </button>
          <button
            type="button"
            class="inline-flex h-8 items-center rounded-lg px-2 text-sm font-medium text-ink-muted transition hover:bg-cloud"
            @click.stop="confirming = false"
          >
            取消
          </button>
        </template>
      </div>

      <button
        type="button"
        class="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg px-2 text-xs font-medium text-ink-muted transition hover:bg-brand/10 hover:text-brand"
        @click.stop="$emit('open-config', schedule)"
      >
        <Icon name="sliders" :size="14" />点击查看配置
      </button>
    </div>
  </article>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'

const props = defineProps({
  schedule: { type: Object, required: true },
  configMeta: { type: Object, required: true }
})
const emit = defineEmits(['toggle', 'open-config', 'delete'])

const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const root = ref(null)
const accent = ref(null)
const knob = ref(null)
const switching = ref(false)
// 删除二次确认态：点击「删除」后展开确认/取消，避免误触
const confirming = ref(false)

function confirmDelete() {
  confirming.value = false
  emit('delete', props.schedule.id)
}

// 登录账号可能是手机号或身份证，辨识度低；有平台回填的真实姓名时优先用它
const displayName = computed(() => props.schedule.studentName || props.schedule.accountName || '—')
// 学院 · 专业：单行展示，超长省略，悬停由 title 看全文
const orgText = computed(() =>
  [props.schedule.college, props.schedule.major].filter(Boolean).join(' · ')
)
// 学号 · 班级 · 账号：单行展示，超长省略，悬停看全文；登录账号仅在姓名存在时补充
const idText = computed(() => {
  const parts = []
  if (props.schedule.studentNo) parts.push(`学号 ${props.schedule.studentNo}`)
  if (props.schedule.className) parts.push(props.schedule.className)
  if (props.schedule.studentName && props.schedule.accountName) parts.push(`账号 ${props.schedule.accountName}`)
  return parts.join(' · ')
})

const statusText = computed(() => {
  if (!props.schedule.accountEnabled) return '账号未启用'
  return props.schedule.enabled ? '运行中' : '已暂停'
})
const statusCls = computed(() => {
  if (!props.schedule.accountEnabled) return 'text-warning'
  return props.schedule.enabled ? 'text-success' : 'text-ink-muted'
})
const modeText = computed(() => (props.schedule.mode === 'follow' ? '跟随配置套' : '自定义时刻'))
const noConfigSet = computed(() => props.schedule.mode === 'follow' && !props.schedule.configSetId)
const nextRunText = computed(() => {
  if (!props.schedule.enabled) return '未开启'
  if (!props.schedule.nextRunAt) return '暂不可执行'
  // nextRunAt 是未叠加随机延迟的基线时刻（后端唯一事实源）；有随机延迟时标注漂移上限
  const jitter = props.schedule.nextRunJitterMin || 0
  return jitter > 0 ? `${props.schedule.nextRunAt}（随机±${jitter}分）` : props.schedule.nextRunAt
})
const lastRunText = computed(() => {
  const s = props.schedule
  if (!s.lastRun) return '暂无记录'
  const label = s.lastStatus === 'success' ? '成功' : s.lastStatus === 'fail' ? '失败' : s.lastStatus === 'skip' ? '跳过' : '—'
  // s.lastRun 已是后端按本地时区格式化的 'YYYY-MM-DD HH:MM'，直接拼接，避免 new Date 时区漂移丢日期
  return `${label} · ${s.lastRun}`
})

// 开关/色条动画：enabled 变化时由 GSAP 平滑过渡
function animateState() {
  if (!knob.value || !accent.value) return
  const on = props.schedule.enabled
  if (prefersReduced) {
    gsap.set(knob.value, { x: on ? 20 : 5 })
    gsap.set(accent.value, { scaleY: on ? 1 : 0 })
    return
  }
  gsap.to(knob.value, { x: on ? 20 : 0, duration: 0.25, ease: 'power2.out' })
  gsap.to(accent.value, { scaleY: on ? 1 : 0, opacity: on ? 1 : 0, duration: 0.3, ease: 'power2.out' })
}

onMounted(async () => {
  await nextTick()
  if (knob.value) gsap.set(knob.value, { x: props.schedule.enabled ? 20 : 0 })
  if (accent.value) gsap.set(accent.value, { scaleY: props.schedule.enabled ? 1 : 0, opacity: props.schedule.enabled ? 1 : 0 })
})

watch(
  () => props.schedule.enabled,
  () => {
    switching.value = true
    animateState()
    setTimeout(() => (switching.value = false), 260)
  }
)
</script>
