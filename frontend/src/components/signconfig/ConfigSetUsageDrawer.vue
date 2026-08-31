<template>
  <div class="fixed inset-0 z-50">
    <!-- 遮罩 -->
    <div ref="overlay" class="absolute inset-0 bg-ink/40" @click="requestClose" />

    <!-- 右滑抽屉面板 -->
    <aside
      ref="panel"
      class="absolute right-0 top-0 flex h-full w-full max-w-lg flex-col bg-white shadow-2xl"
      role="dialog"
      aria-modal="true"
    >
      <header class="flex shrink-0 items-center justify-between gap-3 border-b border-ink/10 px-5 py-4">
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span class="grid h-7 w-7 place-items-center rounded-lg bg-brand/10 text-brand">
              <Icon name="layers" :size="15" />
            </span>
            <h3 class="text-base font-semibold text-ink">套用明细</h3>
          </div>
          <p class="mt-1.5 truncate pl-9 text-xs text-ink-muted">配置套「{{ setName }}」</p>
        </div>
        <button type="button" class="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud" aria-label="关闭" @click="requestClose">
          <Icon name="close" :size="20" />
        </button>
      </header>

      <!-- 规模统计 -->
      <div class="grid shrink-0 grid-cols-2 gap-3 px-5 pt-4">
        <div class="rounded-xl bg-cloud/60 px-3 py-2.5">
          <p class="text-lg font-semibold leading-none text-ink">{{ summary.accountsCount }}</p>
          <p class="mt-1 text-[11px] text-ink-muted">个账号套用</p>
        </div>
        <div class="rounded-xl bg-cloud/60 px-3 py-2.5">
          <p class="text-lg font-semibold leading-none text-ink">{{ summary.instancesCount }}</p>
          <p class="mt-1 text-[11px] text-ink-muted">个任务实例</p>
        </div>
      </div>

      <div class="xb-scroll flex-1 min-h-0 space-y-3 overflow-y-auto px-5 py-4">
        <!-- 空态：尚未有任务套用此套 -->
        <div v-if="detail.length === 0" class="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-ink/10 bg-cloud/30 px-6 py-12 text-center">
          <span class="grid h-12 w-12 place-items-center rounded-full bg-brand/10 text-brand">
            <Icon name="users" :size="22" />
          </span>
          <div>
            <p class="text-sm font-medium text-ink">暂无任务套用此配置套</p>
            <p class="mt-1 text-xs leading-relaxed text-ink-muted">在「账号任务配置」中指定任务套用此套后，<br />使用它的账号与任务会显示在此处。</p>
          </div>
        </div>

        <!-- 按账号分组的台账 -->
        <div v-for="acc in detail" :key="acc.accountId" class="xb-usage-acc rounded-xl border border-ink/10 bg-white/60 p-3">
          <div class="flex items-center gap-2.5">
            <div class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand/10 text-sm font-semibold text-brand">
              {{ acc.accountName.charAt(0) }}
            </div>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-ink">{{ acc.accountName }}</p>
              <p v-if="acc.studentNo" class="truncate text-[11px] text-ink-muted">{{ acc.studentNo }}</p>
            </div>
            <span class="shrink-0 rounded-full bg-ink/5 px-2 py-0.5 text-[11px] font-medium text-ink-soft">{{ acc.tasks.length }} 项</span>
          </div>
          <div class="mt-2.5 flex flex-wrap gap-1.5">
            <button
              v-for="t in acc.tasks"
              :key="t.taskType"
              type="button"
              class="group inline-flex items-center gap-1.5 rounded-full border border-ink/10 bg-white px-2.5 py-1 text-xs text-ink-soft transition hover:border-brand/30 hover:bg-brand/5"
              :title="`查看 ${acc.accountName} 的${t.taskLabel}配置`"
              @click="goTo(acc.accountId, t.taskType)"
            >
              <span class="h-1.5 w-1.5 rounded-full" :class="t.enabled ? 'bg-emerald-500' : 'bg-ink/25'" />
              <span>{{ t.taskLabel }}</span>
              <Icon name="chevron-right" :size="12" class="text-ink-muted transition group-hover:translate-x-0.5 group-hover:text-brand" />
            </button>
          </div>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'
import { useSignConfigStore } from '@/stores/signConfig'

const props = defineProps({
  setId: { type: [String, Number], required: true }
})
const emit = defineEmits(['close'])

const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const overlay = ref(null)
const panel = ref(null)
const closing = ref(false)

const signConfigStore = useSignConfigStore()

const setName = computed(() => signConfigStore.userConfigSets.find((s) => String(s.id) === String(props.setId))?.name || '未知配置套')
const detail = computed(() => signConfigStore.usageDetailOf(props.setId))
const summary = computed(() => signConfigStore.usageSummaryOf(props.setId))

// 跳转到对应账号任务的配置页并关闭抽屉
function goTo(accountId, taskType) {
  signConfigStore.activeTab = 'tasks'
  signConfigStore.selectTask(accountId, taskType)
  requestClose()
}

function revealRows() {
  if (prefersReduced || !panel.value) return
  const rows = panel.value.querySelectorAll('.xb-usage-acc')
  if (rows.length) {
    gsap.fromTo(
      rows,
      { opacity: 0, y: 12 },
      { opacity: 1, y: 0, duration: 0.4, stagger: 0.05, ease: 'power2.out', clearProps: 'opacity,transform' }
    )
  }
}

onMounted(async () => {
  await nextTick()
  if (prefersReduced || !panel.value) {
    revealRows()
    return
  }
  gsap.fromTo(overlay.value, { opacity: 0 }, { opacity: 1, duration: 0.25, ease: 'power2.out' })
  gsap.fromTo(
    panel.value,
    { xPercent: 100 },
    { xPercent: 0, duration: 0.34, ease: 'power3.out', onComplete: revealRows }
  )
})

function requestClose() {
  if (closing.value) return
  closing.value = true
  if (prefersReduced || !panel.value) {
    emit('close')
    return
  }
  gsap.to(overlay.value, { opacity: 0, duration: 0.26, ease: 'power2.in' })
  gsap.to(panel.value, {
    xPercent: 100,
    duration: 0.28,
    ease: 'power3.in',
    onComplete: () => emit('close')
  })
}

onBeforeUnmount(() => {
  gsap.killTweensOf([panel.value, overlay.value])
})
</script>

<style scoped>
.xb-scroll {
  scrollbar-gutter: stable;
}
</style>
