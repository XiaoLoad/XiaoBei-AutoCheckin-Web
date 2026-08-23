<template>
  <div class="flex flex-1 min-h-0 flex-col gap-4 sm:gap-6">
    <!-- ============ 上半区：账户安全（2/5 栏）+ 系统参数（3/5 栏）双栏拼合、等高拉伸 ============ -->
    <!-- 管理员双栏；普通用户仅剩账户安全，退化为单列避免空栏 -->
    <div
      class="grid gap-4 sm:gap-6"
      :class="auth.isAdmin ? 'lg:grid-cols-5' : ''"
    >
      <!-- 区一：账户安全（所有角色可见）：占 2/5 栏宽并与系统参数等高拉伸，按钮沉底填满纵向空间 -->
      <section
        class="dash-card fade-up flex flex-col p-4 sm:p-5"
        :class="auth.isAdmin ? 'lg:col-span-2' : ''"
      >
        <header class="mb-4 flex items-center gap-2">
          <span class="grid h-7 w-7 place-items-center rounded-lg bg-brand/10 text-brand">
            <Icon name="shield" :size="16" />
          </span>
          <h3 class="text-sm font-semibold text-ink">账户安全</h3>
        </header>

        <form class="flex flex-1 flex-col gap-3" @submit.prevent="onChangePassword">
          <div>
            <label class="mb-1 block text-sm font-medium text-ink-soft">原密码</label>
            <input
              v-model="pwdForm.old"
              type="password"
              autocomplete="current-password"
              placeholder="请输入当前密码"
              class="login-input w-full"
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-ink-soft">新密码</label>
            <input
              v-model="pwdForm.next"
              type="password"
              autocomplete="new-password"
              :placeholder="pwdMinHint"
              class="login-input w-full"
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-ink-soft">确认新密码</label>
            <input
              v-model="pwdForm.confirm"
              type="password"
              autocomplete="new-password"
              placeholder="再次输入新密码"
              class="login-input w-full"
              :class="confirmError && 'border-danger focus:border-danger focus:ring-danger/10'"
            />
            <p v-if="confirmError" class="mt-1 text-xs text-danger">{{ confirmError }}</p>
          </div>
          <button
            type="submit"
            class="mt-auto rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-70"
            :disabled="pwdSubmitting || !pwdForm.old || !pwdForm.next || !pwdForm.confirm"
          >
            {{ pwdSubmitting ? '提交中…' : '修改密码' }}
          </button>
        </form>
      </section>

      <!-- 区二：系统参数（仅管理员）：分隔线行式布局，控件右对齐，密度对齐全站设置类页面 -->
      <section v-if="auth.isAdmin" class="dash-card fade-up delay-1 p-4 sm:p-5 lg:col-span-3">
        <header class="mb-1 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="grid h-7 w-7 place-items-center rounded-lg bg-brand/10 text-brand">
              <Icon name="sliders" :size="16" />
            </span>
            <h3 class="text-sm font-semibold text-ink">系统参数</h3>
          </div>
          <button
            v-if="hasDirtyChanges"
            type="button"
            class="text-xs font-medium text-ink-muted transition hover:text-ink"
            @click="resetFormToDefaults"
          >
            恢复默认值
          </button>
        </header>

        <!-- 加载骨架：与行式布局等高的占位 -->
        <div v-if="settingsLoading" class="divide-y divide-ink/5">
          <div v-for="i in 4" :key="i" class="flex items-center justify-between gap-4 py-3.5">
            <div class="space-y-1.5">
              <div class="h-3.5 w-28 rounded bg-ink/5 animate-pulse" />
              <div class="h-3 w-44 rounded bg-ink/5 animate-pulse" />
            </div>
            <div class="h-8 w-20 rounded-lg bg-ink/5 animate-pulse" />
          </div>
        </div>

        <template v-else>
          <div class="divide-y divide-ink/5">
            <div
              v-for="item in settingsItems"
              :key="item.key"
              class="flex items-center justify-between gap-4 py-3.5 first:pt-1 last:pb-1"
            >
              <div class="min-w-0">
                <p class="text-sm font-medium text-ink">
                  {{ item.label }}
                  <span v-if="item.type === 'int'" class="ml-1 text-[11px] font-normal text-ink-muted">
                    {{ item.min }} ~ {{ item.max }}
                  </span>
                </p>
                <p class="mt-0.5 text-xs leading-relaxed text-ink-muted">{{ item.desc }}</p>
              </div>

              <!-- 控件右对齐：开关即拨即存语义（仍由保存按钮统一提交），数字输入窄栏定宽 -->
              <ConfigToggle v-if="item.type === 'bool'" v-model="form[item.key]" class="shrink-0" />
              <input
                v-else
                v-model.number="form[item.key]"
                type="number"
                :min="item.min"
                :max="item.max"
                class="login-input w-full max-w-[120px] shrink-0 px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div class="mt-3 flex flex-wrap items-center gap-3 border-t border-ink/5 pt-3.5">
            <button
              type="button"
              :disabled="saving || !hasDirtyChanges"
              class="rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-70"
              @click="onSaveSettings"
            >
              {{ saving ? '保存中…' : '保存设置' }}
            </button>
            <span class="text-xs text-ink-muted">会话有效期修改后对下一次登录生效</span>
          </div>
        </template>
      </section>
    </div>

    <!-- ============ 区三：系统信息（仅管理员）：整行紧凑指标带 ============ -->
    <section v-if="auth.isAdmin" class="dash-card fade-up delay-2 p-4 sm:p-5">
      <header class="mb-3 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="grid h-7 w-7 place-items-center rounded-lg bg-brand/10 text-brand">
            <Icon name="globe" :size="16" />
          </span>
          <h3 class="text-sm font-semibold text-ink">系统信息</h3>
        </div>
        <button
          type="button"
          class="inline-flex items-center gap-1 text-xs font-medium text-brand transition hover:text-brand-dark hover:underline"
          @click="loadSystemInfo"
        >
          <Icon name="refresh" :size="13" />
          刷新
        </button>
      </header>

      <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        <StatCard label="系统版本" :value="'v' + (sysInfo?.version ?? '-')" icon="box" tone="brand" compact :loading="infoLoading" :delay="1" />
        <StatCard label="运行环境" :value="envLabel" icon="layers" :tone="envTone" compact :loading="infoLoading" :delay="2" />
        <StatCard
          label="已运行时长"
          :value="uptimeLabel"
          icon="clock"
          tone="info"
          compact
          :loading="infoLoading"
          :delay="3"
          :delta="startedAtLabel"
          delta-type="flat"
          delta-hint="本地时间"
        />
        <StatCard
          label="数据库状态"
          :value="dbOk ? '连接正常' : '连接异常'"
          icon="file"
          :tone="dbOk ? 'success' : 'danger'"
          compact
          :loading="infoLoading"
          :delay="4"
        />
        <StatCard
          label="用户规模"
          :value="usersTotal"
          unit="人"
          icon="users"
          tone="brand"
          compact
          :loading="infoLoading"
          :delay="5"
          :delta="usersByRole"
          delta-type="flat"
          delta-hint="按角色"
        />
      </div>
    </section>

    <!-- 底部间距占位：真实在流子元素，盒高计入 scrollHeight，不受滚动容器末端 padding/margin 折叠影响；
         -mt-4 sm:-mt-6 抵消根容器 gap-4 sm:gap-6，确保底部间距精确 24px、与其它页面一致 -->
    <div class="h-6 shrink-0 -mt-4 sm:-mt-6" aria-hidden="true"></div>

    <!-- 轻量提示：右下角深色底，与全站页面动作反馈一致 -->
    <PageToast :show="toast.show" :message="toast.message" :type="toast.type" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import Icon from '@/components/Icon.vue'
import PageToast from '@/components/PageToast.vue'
import StatCard from '@/components/StatCard.vue'
import ConfigToggle from '@/components/signconfig/ConfigToggle.vue'
import * as authApi from '@/api/auth'
import { getSettings, updateSettings, getSystemInfo } from '@/api/settings'
import { useAuthStore } from '@/store/modules/auth'

const auth = useAuthStore()

// ==================== 页面级轻提示（右下角深色底，状态本地持有） ====================
const toast = reactive({ show: false, message: '', type: 'success' })
let toastTimer = null
function showToast(message, type = 'success') {
  toast.message = message
  toast.type = type
  toast.show = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.show = false), 2600)
}

// ==================== 区一：修改密码 ====================
const pwdForm = reactive({ old: '', next: '', confirm: '' })
const pwdSubmitting = ref(false)
const confirmError = ref('')
// 普通用户无权限读取系统参数，仅展示通用建议；精确的最小长度由后端校验并在报错中返回
const minPwdLength = computed(() => {
  const item = settingsItems.value.find((it) => it.key === 'password_min_length')
  return item ? Number(item.current) : 0
})
const pwdMinHint = computed(() =>
  minPwdLength.value
    ? '至少 ' + minPwdLength.value + ' 位，建议混合字母与数字'
    : '建议 8 位以上并混合字母与数字'
)

async function onChangePassword() {
  confirmError.value = ''
  if (pwdForm.next !== pwdForm.confirm) {
    confirmError.value = '两次输入的新密码不一致'
    return
  }
  pwdSubmitting.value = true
  try {
    await authApi.changePassword({ old_password: pwdForm.old, new_password: pwdForm.next })
    showToast('密码修改成功', 'success')
    pwdForm.old = ''
    pwdForm.next = ''
    pwdForm.confirm = ''
  } catch (err) {
    showToast(err.message || '密码修改失败', 'error')
  } finally {
    pwdSubmitting.value = false
  }
}

// ==================== 区二：系统参数（仅管理员） ====================
const settingsItems = ref([])
const form = reactive({})
const defaultsSnapshot = reactive({})
const settingsLoading = ref(false)
const saving = ref(false)

// 与服务端当前值比对：有差异才允许保存并显示"恢复默认值"，避免无意义写库
const hasDirtyChanges = computed(() =>
  settingsItems.value.some((it) => form[it.key] !== undefined && form[it.key] !== it.current)
)

function applyItems(items) {
  settingsItems.value = items || []
  for (const item of settingsItems.value) {
    form[item.key] = item.current
    defaultsSnapshot[item.key] = item.default
  }
}

async function loadSettings() {
  settingsLoading.value = true
  try {
    const data = await getSettings()
    applyItems(data.items)
  } catch (err) {
    showToast(err.message || '系统参数加载失败', 'error')
  } finally {
    settingsLoading.value = false
  }
}

function resetFormToDefaults() {
  for (const item of settingsItems.value) {
    form[item.key] = defaultsSnapshot[item.key]
  }
}

async function onSaveSettings() {
  // 仅提交发生变化的键，减少误覆盖
  const changed = {}
  for (const item of settingsItems.value) {
    if (form[item.key] !== undefined && form[item.key] !== item.current) {
      changed[item.key] = form[item.key]
    }
  }
  if (!Object.keys(changed).length) return

  saving.value = true
  try {
    const data = await updateSettings(changed)
    applyItems(data.items)
    showToast('设置已保存', 'success')
  } catch (err) {
    showToast(err.message || '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

// ==================== 区三：系统信息（仅管理员） ====================
const sysInfo = ref(null)
const infoLoading = ref(false)

const dbOk = computed(() => sysInfo.value?.database?.status === 'ok')
const envLabel = computed(() => {
  if (!sysInfo.value) return '-'
  return sysInfo.value.debug ? '开发环境' : sysInfo.value.env === 'production' ? '生产环境' : sysInfo.value.env
})
const envTone = computed(() => (sysInfo.value?.env === 'production' ? 'success' : 'amber'))
const uptimeLabel = computed(() => formatUptime(sysInfo.value?.uptime_seconds))
const startedAtLabel = computed(() => {
  const raw = sysInfo.value?.started_at
  // 启动时间太长，截取 MM-DD HH:mm 放入副文本位
  return raw ? '启动于 ' + raw.slice(5, 16) : ''
})
const usersTotal = computed(() => String(sysInfo.value?.users?.total ?? '-'))
const usersByRole = computed(() => {
  const u = sysInfo.value?.users
  if (!u) return ''
  return '管理员 ' + u.admins + ' · 用户 ' + u.users
})

function formatUptime(seconds) {
  if (seconds === undefined || seconds === null) return '-'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return d + ' 天 ' + h + ' 小时'
  if (h > 0) return h + ' 小时 ' + m + ' 分'
  return m + ' 分钟'
}

async function loadSystemInfo() {
  infoLoading.value = true
  try {
    sysInfo.value = await getSystemInfo()
  } catch (err) {
    showToast(err.message || '系统信息加载失败', 'error')
  } finally {
    infoLoading.value = false
  }
}

onMounted(() => {
  // 账户安全对所有角色可用；系统参数/系统信息仅管理员加载（后端同样做了 admin 校验）
  if (auth.isAdmin) {
    loadSettings()
    loadSystemInfo()
  }
})
</script>
