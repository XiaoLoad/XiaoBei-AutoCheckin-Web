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
              <Icon name="send" :size="15" />
            </span>
            <h3 class="text-base font-semibold text-ink">批量应用配置套</h3>
          </div>
          <p class="mt-1.5 truncate pl-9 text-xs text-ink-muted">配置套「{{ setName }}」</p>
        </div>
        <button type="button" class="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud" aria-label="关闭" @click="requestClose">
          <Icon name="close" :size="20" />
        </button>
      </header>

      <!-- 覆盖提示 -->
      <div class="mx-5 mt-4 shrink-0 rounded-xl border-l-4 border-amber-400 bg-amber-50 px-3.5 py-2.5 text-xs leading-relaxed text-ink-soft">
        套用会把本套完整配置<strong>覆盖复制</strong>到所选任务（任务转为独立持有该配置快照），不可撤销；已启用任务会立即按新配置重排下一次执行。
      </div>

      <!-- 模糊搜索：账号名称 / 学号 / 班级，空格分词 AND 匹配 -->
      <div class="shrink-0 px-5 pt-3">
        <div class="relative">
          <Icon name="search" :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input
            v-model="query"
            type="text"
            placeholder="搜索账号名称 / 学号 / 班级，空格分隔多关键词"
            class="h-9 w-full rounded-lg border border-ink/10 bg-cloud/40 pl-9 pr-8 text-sm text-ink outline-none transition placeholder:text-ink-muted/70 focus:border-brand/40 focus:bg-white focus:ring-2 focus:ring-brand/10"
          />
          <button
            v-if="query"
            type="button"
            class="absolute right-2 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-md text-ink-muted transition hover:bg-ink/5"
            aria-label="清除搜索"
            @click="query = ''"
          >
            <Icon name="close" :size="14" />
          </button>
        </div>
      </div>

      <!-- 批量工具条：全选 / 反选 / 按类型刷选（已选账号时作用于已选，未选时作用于全部已启用账号） -->
      <div v-if="accounts.length" class="shrink-0 px-5 pt-2.5">
        <div class="flex flex-wrap items-center gap-1.5">
          <span class="text-[11px] text-ink-muted">批量：</span>
          <button
            type="button"
            class="inline-flex h-7 items-center rounded-lg border border-ink/10 bg-white px-2.5 text-xs font-medium text-ink-soft transition hover:border-brand/30 hover:bg-brand/5 hover:text-brand disabled:opacity-50"
            :disabled="applyableAccounts.length === 0"
            @click="selectAllTasks"
          >
            全选
          </button>
          <button
            type="button"
            class="inline-flex h-7 items-center rounded-lg border border-ink/10 bg-white px-2.5 text-xs font-medium text-ink-soft transition hover:border-brand/30 hover:bg-brand/5 hover:text-brand disabled:opacity-50"
            :disabled="applyableAccounts.length === 0"
            @click="invertSelection"
          >
            反选
          </button>
          <span class="mx-0.5 h-4 w-px bg-ink/10" aria-hidden="true"></span>
          <span class="text-[11px] text-ink-muted">按类型：</span>
          <button
            v-for="t in taskTypes"
            :key="t.value"
            type="button"
            class="inline-flex h-7 items-center gap-1.5 rounded-lg border px-2.5 text-xs font-medium transition"
            :class="typeCounts[t.value]
              ? 'border-brand/30 bg-brand/10 text-brand'
              : 'border-ink/10 bg-white text-ink-soft hover:border-brand/30 hover:bg-brand/5 hover:text-brand'"
            :title="brushTitle(t)"
            @click="selectByType(t.value)"
          >
            只选{{ t.label }}
            <span
              v-if="typeCounts[t.value]"
              class="rounded-full bg-brand px-1.5 text-[10px] leading-4 text-white"
            >{{ typeCounts[t.value] }}</span>
          </button>
        </div>
        <p class="mt-1.5 text-[11px] leading-relaxed text-ink-muted">{{ brushHint }}</p>
      </div>

      <!-- 账号列表 -->
      <div class="xb-scroll flex-1 min-h-0 overflow-y-auto px-5 py-4">
        <div v-if="accounts.length === 0" class="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-ink/10 bg-cloud/30 px-6 py-12 text-center">
          <span class="grid h-12 w-12 place-items-center rounded-full bg-brand/10 text-brand">
            <Icon name="users" :size="22" />
          </span>
          <p class="text-sm font-medium text-ink">暂无平台账号</p>
          <p class="text-xs leading-relaxed text-ink-muted">先到「账号管理」添加账号，再回来批量应用配置套。</p>
        </div>

        <div v-else-if="visible.length === 0" class="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-ink/10 bg-cloud/30 px-6 py-10 text-center">
          <p class="text-sm font-medium text-ink">没有匹配「{{ query }}」的账号</p>
          <p class="text-xs text-ink-muted">换个关键词试试，或清空搜索查看全部账号。</p>
        </div>

        <template v-else>
          <div v-for="acc in visible" :key="acc.id" class="xb-apply-acc mb-2.5 rounded-xl border border-ink/10 bg-white/60 p-3">
            <div class="flex items-center gap-2.5">
              <!-- 账号级勾选：一键勾/清该账号全部可应用任务 -->
              <button
                type="button"
                class="grid h-5 w-5 shrink-0 place-items-center rounded-md border transition"
                :class="accChecked(acc.id) ? 'border-brand bg-brand text-white' : 'border-ink/25 bg-white text-transparent hover:border-brand/50'"
                :title="accChecked(acc.id) ? '取消勾选该账号全部任务' : '勾选该账号全部任务'"
                :aria-label="`勾选 ${acc.name} 的全部任务`"
                @click="toggleAccount(acc)"
              >
                <Icon name="check" :size="13" />
              </button>
              <div class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand/10 text-sm font-semibold text-brand">
                {{ acc.name.charAt(0) }}
              </div>
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-medium text-ink">
                  {{ acc.name }}
                  <span v-if="!accEnabled(acc)" class="ml-1.5 rounded-full bg-ink/5 px-1.5 py-0.5 text-[10px] font-normal text-ink-muted">未启用</span>
                </p>
                <p class="truncate text-[11px] text-ink-muted">
                  <template v-if="acc.studentNo">{{ acc.studentNo }}</template>
                  <template v-if="acc.studentNo && acc.className"> · </template>
                  <template v-if="acc.className">{{ acc.className }}</template>
                </p>
              </div>
            </div>
            <!-- 任务级勾选：寝室 / 活动两类，附「已套用」现状徽标 -->
            <div class="ml-7 mt-2.5 flex flex-wrap gap-1.5">
              <button
                v-for="t in taskTypes"
                :key="t.value"
                type="button"
                class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition"
                :class="isChecked(acc.id, t.value)
                  ? 'border-brand bg-brand text-white'
                  : accEnabled(acc)
                    ? 'border-ink/10 bg-white text-ink-soft hover:border-brand/30 hover:bg-brand/5'
                    : 'border-ink/10 bg-white text-ink-muted opacity-60'"
                :disabled="!accEnabled(acc)"
                :title="accEnabled(acc) ? '' : '账号未启用，无法套用'"
                @click="toggleTask(acc.id, t.value)"
              >
                <span class="h-1.5 w-1.5 rounded-full" :class="isChecked(acc.id, t.value) ? 'bg-white' : boundToSet(acc.id, t.value) ? 'bg-brand' : 'bg-ink/25'" />
                <span>{{ t.label }}</span>
                <span
                  v-if="!isChecked(acc.id, t.value) && boundToSet(acc.id, t.value)"
                  class="rounded-full bg-brand/10 px-1.5 text-[10px] leading-4 text-brand"
                >已套用</span>
              </button>
            </div>
          </div>

          <!-- 账号过多：默认截断展示，点击展开全部 -->
          <button
            v-if="filtered.length > visible.length"
            type="button"
            class="mb-1 w-full rounded-xl border border-dashed border-ink/15 py-2.5 text-xs font-medium text-ink-soft transition hover:border-brand/30 hover:bg-brand/5 hover:text-brand"
            @click="cap = filtered.length"
          >
            已显示前 {{ visible.length }} 个，展开全部 {{ filtered.length }} 个账号
          </button>
        </template>
      </div>

      <!-- 底部操作条：统计 + 应用到所选（行内二次确认） -->
      <footer class="shrink-0 border-t border-ink/10 px-5 py-3.5">
        <template v-if="!confirming">
          <div class="flex items-center justify-between gap-3">
            <p class="min-w-0 truncate text-xs text-ink-muted">
              <template v-if="selectedCount">已选 <span class="font-semibold text-ink">{{ selectedCount }}</span> 个任务 · {{ selectedAccountsCount }} 个账号</template>
              <template v-else>勾选账号或任务后套用，可用上方「批量」工具快速选择</template>
            </p>
            <div class="flex shrink-0 items-center gap-2">
              <button
                type="button"
                class="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
                :disabled="selectedCount === 0 || store.saving"
                @click="confirming = true"
              >
                {{ store.saving ? '应用中…' : '应用到所选' }}
              </button>
            </div>
          </div>
        </template>
        <template v-else>
          <div class="flex items-center justify-between gap-3">
            <p class="min-w-0 text-xs leading-relaxed text-ink-soft">
              将把配置套覆盖写入所选 <span class="font-semibold text-ink">{{ selectedCount }}</span> 个任务，此操作不可撤销。
            </p>
            <div class="flex shrink-0 items-center gap-2">
              <button
                type="button"
                class="inline-flex h-9 items-center rounded-lg border border-ink/10 px-3.5 text-sm font-medium text-ink-soft transition hover:bg-cloud"
                @click="confirming = false"
              >
                取消
              </button>
              <button
                type="button"
                class="inline-flex h-9 items-center rounded-lg bg-brand px-4 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
                :disabled="store.saving"
                @click="onApply"
              >
                {{ store.saving ? '应用中…' : '确认套用' }}
              </button>
            </div>
          </div>
        </template>
      </footer>
    </aside>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
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

const store = useSignConfigStore()

const setName = computed(() => store.userConfigSets.find((s) => String(s.id) === String(props.setId))?.name || '未知配置套')
const accounts = computed(() => store.accounts)
const taskTypes = computed(() => store.taskTypes)

const accEnabled = (acc) => acc.status === 'enabled'
// 可参与批量操作的账号全集（已启用）；未启用账号不可勾选、也不参与全选/反选/类型刷选
const applyableAccounts = computed(() => accounts.value.filter(accEnabled))

// ── 选择状态：Set<`${accountId}:${taskType}`>，替换实例保证响应式 ──
const selected = ref(new Set())
const keyOf = (accId, type) => `${accId}:${type}`
const isChecked = (accId, type) => selected.value.has(keyOf(accId, type))
const accChecked = (accId) => (taskTypes.value.length ? taskTypes.value.every((t) => isChecked(accId, t.value)) : false)

function toggleTask(accId, type) {
  const next = new Set(selected.value)
  const k = keyOf(accId, type)
  if (next.has(k)) next.delete(k)
  else next.add(k)
  selected.value = next
}

function toggleAccount(acc) {
  if (!accEnabled(acc)) return
  const next = new Set(selected.value)
  const allOn = accChecked(acc.id)
  for (const t of taskTypes.value) {
    const k = keyOf(acc.id, t.value)
    if (allOn) next.delete(k)
    else next.add(k)
  }
  selected.value = next
}

// 全选：填满所有已启用账号的全部任务类型
function selectAllTasks() {
  const next = new Set()
  for (const acc of applyableAccounts.value) {
    for (const t of taskTypes.value) next.add(keyOf(acc.id, t.value))
  }
  selected.value = next
}

// 反选：对全部已启用账号的每个「账号×任务」键取反
function invertSelection() {
  const next = new Set()
  for (const acc of applyableAccounts.value) {
    for (const t of taskTypes.value) {
      if (!selected.value.has(keyOf(acc.id, t.value))) next.add(keyOf(acc.id, t.value))
    }
  }
  selected.value = next
}

const selectedCount = computed(() => selected.value.size)
const selectedAccountsCount = computed(() => {
  const ids = new Set()
  for (const k of selected.value) ids.add(String(k).split(':')[0])
  return ids.size
})
// 已选账号对应的账号对象（仅已启用）：类型刷选的作用域
const selectedAccounts = computed(() => {
  const ids = new Set()
  for (const k of selected.value) ids.add(String(k).split(':')[0])
  return applyableAccounts.value.filter((a) => ids.has(String(a.id)))
})

// 按类型刷选：把作用域内账号的勾选收敛为「仅该类型」。
// 作用域=已选账号；未选任何账号时作用于全部已启用账号（一步完成「全账号只选某类型」）。
function selectByType(type) {
  const scope = selectedAccounts.value.length ? selectedAccounts.value : applyableAccounts.value
  const next = new Set(selected.value)
  for (const acc of scope) {
    for (const t of taskTypes.value) next.delete(keyOf(acc.id, t.value))
    next.add(keyOf(acc.id, type))
  }
  selected.value = next
}

// 各类型已勾选数：类型按钮上的计数徽标，反馈刷选结果
const typeCounts = computed(() => {
  const counts = {}
  for (const t of taskTypes.value) {
    let n = 0
    for (const k of selected.value) if (k.endsWith(`:${t.value}`)) n++
    counts[t.value] = n
  }
  return counts
})

// 类型刷选的作用域说明（按钮 title 与工具条下方提示共用口径）
const scopeText = computed(() =>
  selectedAccounts.value.length
    ? `已选的 ${selectedAccounts.value.length} 个账号`
    : `全部 ${applyableAccounts.value.length} 个已启用账号`
)
const brushTitle = (t) => `把${scopeText.value}的勾选收敛为仅「${t.label}」`
const brushHint = computed(() =>
  accounts.value.length
    ? `类型刷选作用于${scopeText.value}：点击后这些账号仅保留该类型勾选；先「全选」再点类型即可全账号只跑一种签到。`
    : ''
)

// ── 模糊搜索：大小写不敏感，空格分词后逐词在「名称/学号/班级/平台」里子串匹配（AND）──
const query = ref('')
const norm = (v) => String(v || '').toLowerCase()
const filtered = computed(() => {
  const tokens = norm(query.value).split(/\s+/).filter(Boolean)
  if (!tokens.length) return accounts.value
  return accounts.value.filter((a) => {
    const hay = norm(`${a.name} ${a.studentNo} ${a.className} ${a.platform}`)
    return tokens.every((t) => hay.includes(t))
  })
})
// 账号过多时默认截断到 50 个，底部提供「展开全部」；关键词变化时重置截断
const cap = ref(50)
const visible = computed(() => filtered.value.slice(0, cap.value))
watch(query, () => {
  cap.value = 50
})

// 当前绑定现状：该任务是否已套用本套（展示「已套用」徽标，不做禁选——可重复覆盖）
function boundToSet(accId, type) {
  const b = store.scheduleBindings[keyOf(accId, type)]
  return !!b && b.configSetId != null && String(b.configSetId) === String(props.setId)
}

// 执行：行内二次确认后调用 store；成功（有实际套用）即关闭抽屉
const confirming = ref(false)
async function onApply() {
  const targets = [...selected.value].map((k) => {
    const [accountId, taskType] = k.split(':')
    return { accountId: Number(accountId), taskType }
  })
  const data = await store.applyConfigSetBatch(props.setId, targets)
  if (data && data.updated > 0) requestClose()
  else confirming.value = false
}

function revealRows() {
  if (prefersReduced || !panel.value) return
  const rows = panel.value.querySelectorAll('.xb-apply-acc')
  if (rows.length) {
    gsap.fromTo(
      rows,
      { opacity: 0, y: 12 },
      { opacity: 1, y: 0, duration: 0.4, stagger: 0.04, ease: 'power2.out', clearProps: 'opacity,transform' }
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
