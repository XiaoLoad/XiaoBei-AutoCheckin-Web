<template>
  <div class="flex flex-1 min-h-0 flex-col gap-4 sm:gap-6">
    <!-- ============ 区一：账户安全（所有角色可见） ============ -->
    <section class="dash-card fade-up p-4 sm:p-5">
      <header class="mb-4 flex items-center gap-2">
        <span class="grid h-7 w-7 place-items-center rounded-lg bg-brand/10 text-brand">
          <Icon name="shield" :size="16" />
        </span>
        <h3 class="text-sm font-semibold text-ink">账户安全</h3>
        <span class="text-xs text-ink-muted">当前账号：{{ auth.username }}</span>
      </header>

      <form class="grid gap-4 sm:max-w-md" @submit.prevent="onChangePassword">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">原密码</label>
          <input
            v-model="pwdForm.old"
            type="password"
            autocomplete="current-password"
            placeholder="请输入当前密码"
            class="login-input w-full"
          />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">新密码</label>
          <input
            v-model="pwdForm.next"
            type="password"
            autocomplete="new-password"
            :placeholder="pwdMinHint"
            class="login-input w-full"
          />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">确认新密码</label>
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
        <div class="flex items-center gap-3">
          <button
            type="submit"
            :disabled="pwdSubmitting || !pwdForm.old || !pwdForm.next || !pwdForm.confirm"
            class="inline-flex h-9 items-center justify-center rounded-lg bg-brand px-4 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {{ pwdSubmitting ? '提交中…' : '修改密码' }}
          </button>
        </div>
      </form>
    </section>

    <!-- ============ 区二：系统参数（仅管理员） ============ -->
    <section v-if="auth.isAdmin" class="dash-card fade-up p-4 sm:p-5">
      <header class="mb-4 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="grid h-7 w-7 place-items-center rounded-lg bg-brand/10 text-brand">
            <Icon name="sliders" :size="16" />
          </span>
          <h3 class="text-sm font-semibold text-ink">系统参数</h3>
        </div>
        <button
          v-if="hasDirtyChanges"
          type="button"
          class="text-xs font-medium text-ink-muted hover:text-ink"
          @click="resetFormToDefaults"
        >
          恢复默认值
        </button>
      </header>

      <!-- 加载骨架 -->
      <div v-if="settingsLoading" class="grid gap-3 lg:grid-cols-2">
        <div v-for="i in 4" :key="i" class="h-[76px] animate-pulse rounded-xl bg-ink/5"></div>
      </div>

      <template v-else>
        <div class="grid gap-3 lg:grid-cols-2">
          <div
            v-for="item in settingsItems"
            :key="item.key"
            class="rounded-xl border border-ink/10 bg-white/60 p-3.5"
          >
            <!-- 布尔型：开关行 -->
            <div v-if="item.type === 'bool'" class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="text-sm font-medium text-ink">{{ item.label }}</p>
                <p class="mt-0.5 text-xs leading-relaxed text-ink-muted">{{ item.desc }}</p>
              </div>
              <ConfigToggle v-model="form[item.key]" />
            </div>

            <!-- 整型：数字输入行 -->
            <div v-else>
              <div class="flex items-baseline justify-between gap-2">
                <p class="text-sm font-medium text-ink">{{ item.label }}</p>
                <span class="shrink-0 text-[11px] text-ink-muted">范围 {{ item.min }} ~ {{ item.max }}</span>
              </div>
              <input
                v-model.number="form[item.key]"
                type="number"
                :min="item.min"
                :max="item.max"
                class="login-input mt-2 w-full sm:w-40"
              />
              <p class="mt-1 text-xs leading-relaxed text-ink-muted">{{ item.desc }}</p>
            </div>
          </div>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            :disabled="saving || !hasDirtyChanges"
            class="inline-flex h-9 items-center justify-center rounded-lg bg-brand px-4 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            @click="onSaveSettings"
          >
            {{ saving ? '保存中…' : '保存设置' }}
          </button>
          <span class="text-xs text-ink-muted">会话有效期修改后对下一次登录生效</span>
        </div>
      </template>
    </section>

    <!-- ============ 区三：系统信息（仅管理员） ============ -->
    <section v-if="auth.isAdmin" class="dash-card fade-up p-4 sm:p-5">
      <header class="mb-4 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="grid h-7 w-7 place-items-center rounded-lg bg-brand/10 text-brand">
            <Icon name="globe" :size="16" />
          </span>
          <h3 class="text-sm font-semibold text-ink">系统信息</h3>
        </div>
        <button
          type="button"
          class="inline-flex items-center gap-1 text-xs font-medium text-brand hover:underline"
          @click="loadSystemInfo"
        >
          <Icon name="refresh" :size="13" />
          刷新
        </button>
      </header>

      <div v-if="infoLoading" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div v-for="i in 6" :key="i" class="h-16 animate-pulse rounded-xl bg-ink/5"></div>
      </div>

      <div v-else-if="sysInfo" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <InfoTile label="系统版本" :value="'v' + sysInfo.version" icon="box" />
        <InfoTile label="运行环境" icon="layers">
          <span
            class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
            :class="envBadgeCls"
          >
            {{ envLabel }}
          </span>
        </InfoTile>
        <InfoTile label="已运行时长" :value="uptimeLabel" icon="clock" />
        <InfoTile label="本次启动时间" :value="sysInfo.started_at" icon="calendar" />
        <InfoTile label="数据库状态" icon="file">
          <span
            class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
            :class="dbOk ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'"
          >
            <span class="h-1.5 w-1.5 rounded-full" :class="dbOk ? 'bg-success' : 'bg-danger'" />
            {{ dbOk ? '连接正常' : '连接异常' }}
          </span>
        </InfoTile>
        <InfoTile label="用户规模" icon="users" :value="usersSummary" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import Icon from '@/components/Icon.vue'
import InfoTile from '@/components/InfoTile.vue'
import ConfigToggle from '@/components/signconfig/ConfigToggle.vue'
import * as authApi from '@/api/auth'
import { getSettings, updateSettings, getSystemInfo } from '@/api/settings'
import { useAuthStore } from '@/store/modules/auth'
import toast from '@/utils/toast'

const auth = useAuthStore()

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
    toast('密码修改成功', 'success')
    pwdForm.old = ''
    pwdForm.next = ''
    pwdForm.confirm = ''
  } catch (err) {
    toast(err.message || '密码修改失败', 'error')
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
    toast(err.message || '系统参数加载失败', 'error')
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
    toast('设置已保存', 'success')
  } catch (err) {
    toast(err.message || '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

// ==================== 区三：系统信息（仅管理员） ====================
const sysInfo = ref(null)
const infoLoading = ref(false)

const dbOk = computed(() => sysInfo.value?.database?.status === 'ok')
const envLabel = computed(() => {
  if (!sysInfo.value) return ''
  return sysInfo.value.debug ? '开发环境' : sysInfo.value.env === 'production' ? '生产环境' : sysInfo.value.env
})
const envBadgeCls = computed(() =>
  sysInfo.value?.env === 'production' ? 'bg-success/10 text-success' : 'bg-amber/15 text-amber'
)
const uptimeLabel = computed(() => formatUptime(sysInfo.value?.uptime_seconds))
const usersSummary = computed(() => {
  const u = sysInfo.value?.users
  if (!u) return '-'
  return u.total + ' 人（管理员 ' + u.admins + ' / 用户 ' + u.users + '）'
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
    toast(err.message || '系统信息加载失败', 'error')
  } finally {
    infoLoading.value = false
  }
}

onMounted(() => {
  // 区一对所有角色可用；区二/区三仅管理员加载（后端同样做了 admin 校验）
  if (auth.isAdmin) {
    loadSettings()
    loadSystemInfo()
  }
})
</script>
