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
            @click="onStrategy(m.value)"
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

        <!-- 自动签到时机：用户语言描述，替代"开窗/关窗"术语 -->
        <div>
          <label class="mb-1.5 block text-xs font-medium text-ink-muted">自动签到时机</label>
          <div class="space-y-2.5">
            <div class="flex items-center gap-2">
              <span class="shrink-0 text-xs text-ink-muted">上课前</span>
              <input
                v-model.number="config.activity.course.leadMinutes"
                type="number" min="0" max="120"
                class="w-20 rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
              />
              <span class="text-xs text-ink-muted">分钟开始留意签到</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="shrink-0 text-xs text-ink-muted">下课后继续留意</span>
              <input
                v-model.number="config.activity.course.tailMinutes"
                type="number" min="0" max="120"
                class="w-20 rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
              />
              <span class="text-xs text-ink-muted">分钟</span>
            </div>
          </div>
          <p class="mt-1.5 text-xs leading-relaxed text-ink-muted">
            有课的日子，从上课前到下课后这段时间里，系统会自动留意老师发布的签到并代签；没课的日子完全不打扰。
          </p>
        </div>

        <!-- 高级：查询频率（渐进披露，默认收起） -->
        <div>
          <button
            type="button"
            class="flex items-center gap-1 text-xs text-ink-muted transition hover:text-ink-soft"
            @click="showAdvanced = !showAdvanced"
          >
            <Icon name="chevron" :size="13" :class="showAdvanced ? 'rotate-90 transition' : 'transition'" />高级 · 查询频率
          </button>
          <div v-if="showAdvanced" class="mt-2 flex flex-wrap items-center gap-2 rounded-lg bg-cloud px-3 py-2">
            <span class="text-xs text-ink-muted">留意时段内每</span>
            <input
              v-model.number="config.activity.course.pollIntervalSec"
              type="number" min="30" max="1800" step="30"
              class="w-20 rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
            />
            <span class="text-xs text-ink-muted">秒检查一次（默认 120 秒，一般无需修改）</span>
          </div>
        </div>

        <!-- 每日兜底 -->
        <div>
          <label class="flex cursor-pointer items-center gap-2">
            <input v-model="config.activity.fallback.enabled" type="checkbox" class="h-4 w-4 accent-brand" />
            <span class="text-sm text-ink">每天固定时刻也查一次临时活动</span>
          </label>
          <p class="mt-1 text-xs leading-relaxed text-ink-muted">
            按上方「时间配置」的时刻，每天额外查询一次——覆盖不按课表上的实践课与临时活动；关闭则只跟课表走。
          </p>
        </div>

        <!-- 课表与调度入口 + 当日窗口预览（需账号与课表数据） -->
        <template v-if="accountId">
          <div>
            <div class="flex items-center justify-between gap-2 rounded-lg bg-cloud px-3 py-2.5">
              <span class="min-w-0 truncate text-xs text-ink-soft">{{ scheduleSummary }}</span>
              <button
                type="button"
                class="inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-brand/30 bg-brand/5 px-3 text-xs font-medium text-brand transition hover:bg-brand/10 disabled:opacity-40"
                :disabled="!overview?.bound"
                @click="showTimetable = true"
              >
                <Icon name="calendar" :size="13" />查看课表与调度
              </button>
            </div>
            <p class="mt-1.5 text-xs text-ink-muted">在课表上点亮要自动签到的课、熄灭不参与的时段；改动随任务保存生效。</p>
          </div>

          <div v-if="todayWindows.length">
            <label class="mb-1.5 block text-xs font-medium text-ink-muted">今日安排</label>
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
                <span class="shrink-0">{{ w.done ? '已结束' : '留意中' }}</span>
              </li>
            </ul>
          </div>
        </template>
      </template>
    </div>

    <!-- 课表与调度抽屉（块级开关，写入 excludeBlocks 草稿） -->
    <ActivityTimetableDrawer
      v-if="showTimetable && accountId"
      :account-id="accountId"
      :config="config"
      @close="showTimetable = false"
    />
  </ConfigSection>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import Icon from '@/components/Icon.vue'
import ActivityTimetableDrawer from '@/components/signconfig/ActivityTimetableDrawer.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { useJwxtStore } from '@/stores/jwxt'
import { ensureActivityConfig } from '@/api/signConfig'

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

// 骨架兜底：历史/脏数据的 activity 可能是 {} 或缺 course/fallback 内层，模板深绑定
// course.leadMinutes 会崩；挂载/换配置时就地补齐。
watch(
  () => props.config,
  (cfg) => ensureActivityConfig(cfg?.activity),
  { immediate: true }
)
// 切换策略前强制补齐一次：无论 activity 处于什么残缺形状，深绑定都不至于踩空
function onStrategy(v) {
  ensureActivityConfig(props.config.activity)
  props.config.activity.strategy = v
}

const overview = computed(() => (props.accountId ? jwxtStore.overviewOf(props.accountId) : null))
// 同步进行中：本会话已提交（syncing）或后端队列仍在执行（syncRunning，跨页面/刷新后仍可见）
const isSyncing = computed(() => {
  const key = String(props.accountId || '')
  return !!jwxtStore.syncing[key] || !!overview.value?.syncRunning
})
const className = computed(() => overview.value?.className || '')
const todayWindows = computed(() => overview.value?.windows || [])

// 课表抽屉与调度摘要
const showTimetable = ref(false)
const showAdvanced = ref(false)
const scheduleSummary = computed(() => {
  if (!overview.value?.bound) return '绑定教务账号并同步课表后，可按课程安排自动签到'
  const blocks = overview.value.courses || []
  const excluded = props.config.activity?.course?.excludeBlocks || []
  const legacyNames = props.config.activity?.course?.excludeCourses || []
  const excludedCount = blocks.filter((b) => excluded.includes(b.blockKey) || legacyNames.includes(b.course)).length
  const active = blocks.length - excludedCount
  return excludedCount
    ? `${active} 个时段参与调度 · ${excludedCount} 个已排除`
    : `${blocks.length} 个时段全部参与调度`
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
