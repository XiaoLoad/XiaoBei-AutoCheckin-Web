<template>
  <div class="flex flex-1 min-h-0 flex-col gap-4 sm:gap-6">
    <!--
      总布局：分割线行置于卡片外、每个模块独立成卡。
      管理员：左列「账户安全」「系统参数」两张白卡纵排；
              右列深墨蓝状态舱跨双行与左列等高，体征列表沉底对齐；
      普通用户：无系统参数/系统信息权限，退化为单列单卡。
    -->
    <div
      class="grid items-stretch gap-4 sm:gap-5"
      :class="auth.isAdmin ? 'lg:grid-cols-[minmax(0,1fr)_340px]' : ''"
    >
      <!-- ===== 模块一：账户安全（所有角色）：分割线行在卡外，独立成卡 ===== -->
      <section class="fade-up min-w-0" aria-labelledby="settings-hd-account">
        <!-- 分割线行：大写标签 + 延伸细线 + 右侧弱化提示，与仪表盘「全站汇总」同款 -->
        <div class="mb-3 flex items-center gap-2">
          <h2 id="settings-hd-account" class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">账户安全</h2>
          <span class="h-px flex-1 bg-ink/10" aria-hidden="true"></span>
          <span class="text-xs text-ink-muted">所有角色</span>
        </div>

        <div class="dash-card p-4 sm:p-5">
          <!-- 三字段一行排开，动作右置：控制台密度 -->
          <form class="grid gap-3 sm:grid-cols-3" @submit.prevent="onChangePassword">
            <div>
              <label class="mb-1 block text-xs font-medium text-ink-muted">原密码</label>
              <input
                v-model="pwdForm.old"
                type="password"
                autocomplete="current-password"
                placeholder="输入当前密码"
                class="login-input px-3 py-2.5 text-sm"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-ink-muted">新密码</label>
              <input
                v-model="pwdForm.next"
                type="password"
                autocomplete="new-password"
                :placeholder="pwdMinHint"
                class="login-input px-3 py-2.5 text-sm"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-ink-muted">确认新密码</label>
              <input
                v-model="pwdForm.confirm"
                type="password"
                autocomplete="new-password"
                placeholder="再次输入新密码"
                class="login-input px-3 py-2.5 text-sm"
                :class="confirmError && 'border-danger focus:border-danger focus:ring-danger/10'"
              />
              <p v-if="confirmError" class="mt-1 text-xs text-danger">{{ confirmError }}</p>
            </div>
            <div class="flex justify-end sm:col-span-3">
              <button
                type="submit"
                class="rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-70"
                :disabled="pwdSubmitting || !pwdForm.old || !pwdForm.next || !pwdForm.confirm"
              >
                {{ pwdSubmitting ? '提交中…' : '修改密码' }}
              </button>
            </div>
          </form>
        </div>
      </section>

      <!-- ===== 模块二：系统参数（仅管理员）：独立成卡 ===== -->
      <section v-if="auth.isAdmin" class="fade-up delay-1 min-w-0" aria-labelledby="settings-hd-params">
        <!-- 分割线行在卡外 -->
        <div class="mb-3 flex items-center gap-2">
          <h2 id="settings-hd-params" class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">系统参数</h2>
          <span class="h-px flex-1 bg-ink/10" aria-hidden="true"></span>
          <span class="text-xs text-ink-muted">仅管理员</span>
        </div>

        <div class="dash-card p-4 sm:p-5">
          <!-- 加载骨架：与行式布局等高的占位 -->
          <div v-if="settingsLoading" class="divide-y divide-ink/5">
            <div v-for="i in 4" :key="i" class="flex items-center justify-between gap-4 py-3">
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
                class="flex items-center justify-between gap-4 py-3 first:pt-1 last:pb-1"
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

            <!-- 底部操作区：主操作「保存设置」+ 条件出现的「恢复默认值」+ 说明文字推至右端 -->
            <div class="mt-3 flex flex-wrap items-center gap-3 border-t border-ink/5 pt-3">
              <button
                type="button"
                :disabled="saving || !hasDirtyChanges"
                class="rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-70"
                @click="onSaveSettings"
              >
                {{ saving ? '保存中…' : '保存设置' }}
              </button>
              <button
                v-if="hasDirtyChanges"
                type="button"
                class="text-xs font-medium text-ink-muted transition hover:text-ink"
                @click="resetFormToDefaults"
              >
                恢复默认值
              </button>
              <span class="ml-auto text-xs text-ink-muted">会话有效期修改后对下一次登录生效</span>
            </div>
          </template>
        </div>
      </section>

      <!-- ===== 模块三：系统信息（仅管理员）：右列跨双行与左列等高，分割线行在卡外 ===== -->
      <section
        v-if="auth.isAdmin"
        aria-labelledby="settings-hd-info"
        class="fade-up delay-2 flex min-w-0 flex-col lg:col-start-2 lg:row-start-1 lg:row-span-2"
      >
        <!-- 分割线行的暗色变体：标签 + 细线 + 刷新控件 -->
        <div class="mb-3 flex items-center gap-2">
          <h2 id="settings-hd-info" class="text-[11px] font-semibold uppercase tracking-wider text-white/55">系统信息</h2>
          <span class="h-px flex-1 bg-white/15" aria-hidden="true"></span>
          <button
            type="button"
            class="inline-flex items-center gap-1 text-xs font-medium text-white/60 transition hover:text-white"
            @click="loadSystemInfo"
          >
            <Icon name="refresh" :size="13" />
            刷新
          </button>
        </div>

        <!-- 签名元素：深墨蓝状态舱 —— 与侧边栏/登录页同源身份色，全页唯一深色块；
             flex-1 填满本模块剩余高度，体征列表沉底与左列底缘共线 -->
        <div
          class="flex flex-1 flex-col rounded-2xl bg-ink p-5 ring-1 ring-white/10 shadow-[0_1px_2px_rgba(20,33,61,0.04),0_18px_40px_-20px_rgba(20,33,61,0.45)]"
        >
          <!-- 加载骨架：与「版本主值 + 沉底体征列表」的最终几何同构 -->
          <div v-if="infoLoading" class="mt-6">
            <div class="space-y-2.5">
              <div class="h-2.5 w-16 rounded bg-white/15 animate-pulse" />
              <div class="h-8 w-36 rounded bg-white/15 animate-pulse" />
              <div class="h-6 w-28 rounded-full bg-white/10 animate-pulse" />
            </div>
            <div class="mt-8 divide-y divide-white/10 border-t border-white/10">
              <div v-for="i in 3" :key="i" class="flex items-center justify-between py-3.5">
                <div class="h-2.5 w-14 rounded bg-white/15 animate-pulse" />
                <div class="h-4 w-20 rounded bg-white/15 animate-pulse" />
              </div>
            </div>
          </div>

          <template v-else>
            <!-- 版本是唯一主值：等宽字体强化工程感；环境降为描边徽标 + 状态点 -->
            <p class="mt-6 text-[11px] font-semibold uppercase tracking-wider text-white/50">系统版本</p>
            <p class="mt-2 font-mono text-[30px] font-semibold leading-none tracking-tight text-white">v{{ sysInfo?.version ?? '-' }}</p>
            <span class="mt-3.5 inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium text-white/85 ring-1 ring-white/20">
              <span class="h-1.5 w-1.5 rounded-full" :class="envDotCls"></span>
              {{ envLabel }}
            </span>

            <!-- 体征列表：mt-auto 沉底，与左列卡片区底缘共线；定义列表语义 -->
            <div class="mt-auto pt-6">
              <dl class="divide-y divide-white/10 border-t border-white/10">
                <div class="flex items-center justify-between gap-3 py-3.5">
                  <dt class="text-[11px] font-semibold uppercase tracking-wider text-white/50">数据库</dt>
                  <dd class="flex items-center gap-2 text-sm font-semibold tabular-nums text-white">
                    <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="dbOk ? 'bg-success brand-dot' : 'bg-danger'"></span>
                    {{ dbOk ? '连接正常' : '连接异常' }}
                  </dd>
                </div>
                <div class="py-3.5">
                  <div class="flex items-baseline justify-between gap-3">
                    <dt class="text-[11px] font-semibold uppercase tracking-wider text-white/50">已运行时长</dt>
                    <dd class="truncate text-sm font-semibold tabular-nums text-white">{{ uptimeLabel }}</dd>
                  </div>
                  <p v-if="startedAtLabel" class="mt-1 text-right text-xs text-white/45">{{ startedAtLabel }}</p>
                </div>
                <div class="py-3.5">
                  <div class="flex items-baseline justify-between gap-3">
                    <dt class="text-[11px] font-semibold uppercase tracking-wider text-white/50">用户规模</dt>
                    <dd class="text-sm font-semibold tabular-nums text-white">{{ usersTotal }} 人</dd>
                  </div>
                  <p class="mt-1 text-right text-xs text-white/45">管理员 {{ sysInfo?.users?.admins ?? '-' }} · 用户 {{ sysInfo?.users?.users ?? '-' }}</p>
                </div>
              </dl>
            </div>
          </template>
        </div>
      </section>
    </div>

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
import ConfigToggle from '@/components/signconfig/ConfigToggle.vue'
import * as authApi from '@/api/auth'
import { getSettings, updateSettings, getSystemInfo } from '@/api/settings'
import { useAuthStore } from '@/stores/auth'

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
// 最近一次刷新时间（HH:mm:ss）：让刷新按钮有可感知的结果反馈
const lastRefreshed = ref('')

const dbOk = computed(() => sysInfo.value?.database?.status === 'ok')
// 环境状态点：生产绿（稳定信号）/ 非生产琥珀（提示信号）；徽标文字恒白，颜色只落在圆点上
const envDotCls = computed(() =>
  sysInfo.value?.env === 'production' ? 'bg-success' : 'bg-amber'
)
const envLabel = computed(() => {
  if (!sysInfo.value) return '-'
  return sysInfo.value.debug ? '开发环境' : sysInfo.value.env === 'production' ? '生产环境' : sysInfo.value.env
})
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
    lastRefreshed.value = new Date().toTimeString().slice(0, 8)
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
