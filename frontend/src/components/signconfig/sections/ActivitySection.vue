<template>
  <ConfigSection title="活动调度策略" icon="calendar" :source="source" :error="error">
    <div class="space-y-4">
      <!-- 调度策略：固定时刻沿用时间配置；课表驱动按教务课表展开时间窗 -->
      <div>
        <label class="mb-1.5 block text-xs font-medium text-ink-muted">调度方式</label>
        <div class="inline-flex rounded-xl bg-cloud p-1">
          <button
            v-for="m in strategies"
            :key="m.value"
            type="button"
            class="rounded-lg px-3 py-1.5 text-sm font-medium transition"
            :class="config.activity.strategy === m.value ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
            @click="config.activity.strategy = m.value"
          >
            {{ m.label }}
          </button>
        </div>
        <p class="mt-1.5 text-xs text-ink-muted">
          {{ config.activity.strategy === 'fixed' ? '按上方「时间配置」的定时时刻每天查询一次活动，适合时间固定的活动签到。' : '按教务课表在有课的日子自动开窗轮询（课程前后），无课日零查询；需绑定教务账号并同步课表。' }}
        </p>
      </div>

      <template v-if="config.activity.strategy === 'course'">
        <!-- 模板模式（配置套）：无账号上下文，只调参数 -->
        <div v-if="!accountId" class="flex items-start gap-2 rounded-xl bg-brand/5 px-3 py-2.5 text-xs leading-relaxed text-ink-soft">
          <Icon name="info" :size="14" class="mt-0.5 shrink-0 text-brand" />
          <span>这是配置套模板。教务账号绑定、课表同步与本周窗口预览请在「账号任务配置 → 活动签到」节点按账号操作；此处参数会随套用复制到各账号任务。</span>
        </div>

        <!-- 教务绑定卡（账号任务节点专属） -->
        <div v-if="accountId" class="rounded-xl border border-ink/10 bg-cloud/60 p-3">
          <div class="mb-2 flex items-center justify-between gap-2">
            <span class="text-xs font-medium text-ink-soft">教务账号</span>
            <span
              v-if="overview?.bound"
              class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium"
              :class="overview.account.status === 'needs_attention' ? 'bg-warning/10 text-warning' : 'bg-success/10 text-success'"
            >
              <span class="h-1.5 w-1.5 rounded-full bg-current" />
              {{ overview.account.status === 'needs_attention' ? '同步异常' : '已绑定' }}
            </span>
          </div>

          <!-- 未绑定：学号预填 + 密码录入 -->
          <div v-if="!overview?.bound" class="space-y-2">
            <div class="flex items-center gap-2">
              <div class="w-36">
                <input
                  v-model="bindForm.studentNo"
                  type="text"
                  inputmode="numeric"
                  placeholder="教务学号"
                  class="w-full rounded-lg border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
                />
              </div>
              <div class="min-w-0 flex-1">
                <input
                  v-model="bindForm.password"
                  type="password"
                  autocomplete="new-password"
                  placeholder="教务系统登录密码"
                  class="w-full rounded-lg border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
                />
              </div>
              <button
                type="button"
                class="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg bg-brand px-3.5 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
                :disabled="!bindForm.studentNo || !bindForm.password || isSyncing"
                @click="onBind"
              >
                <Icon name="lock" :size="13" />{{ isSyncing ? '同步中…' : '绑定并同步' }}
              </button>
            </div>
            <p class="text-[11px] leading-relaxed text-ink-muted">密码仅用于服务端登录教务系统拉取课表，加密存储、不会出现在日志中。连续失败会触发教务验证码，请稍后再试。</p>
          </div>

          <!-- 已绑定：概览 + 立即同步 / 解绑 -->
          <div v-else class="space-y-2.5">
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-soft">
              <span>学号 <b class="font-medium text-ink">{{ overview.account.studentNo }}</b></span>
              <span v-if="className" class="text-ink-muted">{{ className }}</span>
              <span v-if="overview.semester" class="rounded-md bg-white px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">{{ overview.semester.semester }}</span>
              <span v-if="overview.timetableSyncedAt" class="text-ink-muted">同步于 {{ overview.timetableSyncedAt }}</span>
              <span v-if="overview.account.lastError" class="text-warning">{{ overview.account.lastError }}</span>
            </div>
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-brand/30 px-3 text-sm font-medium text-brand transition hover:bg-brand/10 disabled:opacity-50"
                :disabled="isSyncing"
                @click="onSync"
              >
                <Icon name="refresh" :size="13" />{{ isSyncing ? '同步中…' : '立即同步' }}
              </button>
              <button
                type="button"
                class="inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-sm text-ink-muted transition hover:bg-white disabled:opacity-40"
                :disabled="isSyncing"
                @click="onUnbind"
              >
                <Icon name="close" :size="13" />解绑
              </button>
            </div>
          </div>
        </div>

        <!-- 窗口参数 -->
        <div>
          <label class="mb-1.5 block text-xs font-medium text-ink-muted">轮询窗口参数</label>
          <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
            <div class="flex items-center gap-1.5">
              <span class="text-xs text-ink-muted">课前提前</span>
              <input
                v-model.number="config.activity.course.leadMinutes"
                type="number" min="0" max="120"
                class="w-20 rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
              />
              <span class="text-xs text-ink-muted">分开窗</span>
            </div>
            <div class="flex items-center gap-1.5">
              <span class="text-xs text-ink-muted">课后延续</span>
              <input
                v-model.number="config.activity.course.tailMinutes"
                type="number" min="0" max="120"
                class="w-20 rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
              />
              <span class="text-xs text-ink-muted">分关窗</span>
            </div>
            <div class="flex items-center gap-1.5">
              <span class="text-xs text-ink-muted">每</span>
              <input
                v-model.number="config.activity.course.pollIntervalSec"
                type="number" min="30" max="1800" step="30"
                class="w-20 rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
              />
              <span class="text-xs text-ink-muted">秒查询一次</span>
            </div>
          </div>
          <p class="mt-1.5 text-xs text-ink-muted">窗口内按间隔查询活动发布情况，查到即自动签到；未查到不产生任何记录。</p>
        </div>

        <!-- 每日兜底 -->
        <div>
          <label class="flex cursor-pointer items-center gap-2">
            <input v-model="config.activity.fallback.enabled" type="checkbox" class="h-4 w-4 accent-brand" />
            <span class="text-sm text-ink">每日兜底查询</span>
          </label>
          <p class="mt-1 text-xs leading-relaxed text-ink-muted">
            开启后仍按上方「时间配置」的时刻每天查询一次，覆盖无固定节次的实践课与临时活动；关闭则完全依赖课表窗口（无课日零查询）。
          </p>
        </div>

        <!-- 课程排除 + 当日窗口预览（需账号与课表数据） -->
        <template v-if="accountId">
          <div>
            <label class="mb-1.5 block text-xs font-medium text-ink-muted">不参与调度的课程</label>
            <div v-if="courseNames.length" class="flex flex-wrap gap-1.5">
              <button
                v-for="c in courseNames"
                :key="c"
                type="button"
                class="rounded-lg border px-3 py-1.5 text-sm transition"
                :class="isExcluded(c) ? 'border-ink/10 bg-ink/5 text-ink-muted line-through' : 'border-brand/40 bg-brand/5 text-ink-soft hover:bg-brand/10'"
                :title="isExcluded(c) ? '点击恢复该课程的课表调度' : '点击排除该课程（不展开轮询窗口）'"
                @click="toggleExclude(c)"
              >
                {{ c }}
              </button>
            </div>
            <p v-else class="rounded-lg bg-cloud px-3 py-2 text-xs text-ink-muted">
              {{ overview?.bound ? '课表暂无课程数据，可尝试「立即同步」。' : '绑定教务账号并同步课表后，可在此排除不需要调度的课程（如毕业实习）。' }}
            </p>
          </div>

          <div v-if="todayWindows.length">
            <label class="mb-1.5 block text-xs font-medium text-ink-muted">今日轮询窗口</label>
            <ul class="space-y-1">
              <li
                v-for="w in todayWindows"
                :key="w.id"
                class="flex items-center gap-2 rounded-lg bg-cloud px-3 py-1.5 text-xs"
                :class="w.done ? 'text-ink-muted' : 'text-ink-soft'"
              >
                <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="w.done ? 'bg-ink/20' : 'bg-success'" />
                <span class="min-w-0 flex-1 truncate">{{ w.courseName || '未命名课程' }}</span>
                <span class="shrink-0 font-mono">{{ shortTime(w.startAt) }} ~ {{ shortTime(w.endAt) }}</span>
                <span class="shrink-0">{{ w.done ? '已结束' : '待轮询' }}</span>
              </li>
            </ul>
          </div>
        </template>
      </template>
    </div>
  </ConfigSection>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import Icon from '@/components/Icon.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { useJwxtStore } from '@/stores/jwxt'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' },
  error: { type: String, default: '' },
  // 所属 B 平台账号 id（账号任务节点传入；配置套模板不传，隐藏绑定/预览区）
  accountId: { type: String, default: '' }
})

const signConfigStore = useSignConfigStore()
const jwxtStore = useJwxtStore()

const strategies = [
  { value: 'fixed', label: '固定时刻' },
  { value: 'course', label: '按课表自动' }
]

const overview = computed(() => (props.accountId ? jwxtStore.overviewOf(props.accountId) : null))
// 同步进行中：本会话已提交（syncing）或后端队列仍在执行（syncRunning，跨页面/刷新后仍可见）
const isSyncing = computed(() => {
  const key = String(props.accountId || '')
  return !!jwxtStore.syncing[key] || !!overview.value?.syncRunning
})
const className = computed(() => overview.value?.className || '')
const todayWindows = computed(() => overview.value?.windows || [])
// 去重后的课程名清单（同一课程不同周次/节次只出现一次）
const courseNames = computed(() => {
  const set = new Set()
  for (const c of overview.value?.courses || []) set.add(c.course)
  return Array.from(set)
})

// 绑定表单：学号默认取 B 平台档案回填的学号（与教务学号一致，设计文档 §4.4）
const bindForm = reactive({ studentNo: '', password: '' })
watch(
  [() => props.accountId, () => overview.value?.bound],
  ([id]) => {
    if (!id) return
    const acc = signConfigStore.accounts.find((a) => String(a.id) === String(id))
    bindForm.studentNo = acc?.studentNo || ''
    bindForm.password = ''
  },
  { immediate: true }
)

// 切到课表策略时预取该账号的教务概览（未绑定则渲染绑定表单）
watch(
  () => [props.accountId, props.config.activity?.strategy],
  ([id, strategy]) => {
    if (id && strategy === 'course') jwxtStore.load(id)
  },
  { immediate: true }
)

function isExcluded(name) {
  return (props.config.activity.course.excludeCourses || []).includes(name)
}
function toggleExclude(name) {
  const list = props.config.activity.course.excludeCourses
  const i = list.indexOf(name)
  if (i === -1) list.push(name)
  else list.splice(i, 1)
}

async function onBind() {
  const ok = await jwxtStore.bind(props.accountId, {
    studentNo: bindForm.studentNo.trim(),
    password: bindForm.password
  })
  if (ok) bindForm.password = ''
}

async function onSync() {
  await jwxtStore.sync(props.accountId)
}

async function onUnbind() {
  if (!window.confirm('解绑后将清除已同步的课表，课表调度回落为每日兜底查询。确定解绑吗？')) return
  await jwxtStore.unbind(props.accountId)
}

function shortTime(s) {
  // "2026-09-07 08:05" → "08:05"；异常原样返回
  const m = String(s || '').match(/(\d{2}:\d{2})(?::\d{2})?$/)
  return m ? m[1] : s
}
</script>
