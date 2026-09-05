<template>
  <div class="flex flex-col gap-5 lg:flex-1 lg:min-h-0">
    <!--
      总布局：按「账户 / 系统」两组分区，组头为「标签 + 延伸细线 + 提示」，组内模块各自成卡、全部通栏。
      系统参数卡内按业务语义二次分组（注册与额度 / 账号安全 / 数据治理 / 地图服务，未识别键兜底进「其他参数」），
      每组带图标章 + 一句话定位；短组 xl 双列网格，长文本组（地图服务）通栏不挤压描述。
      控件右置规范化：数字输入右对齐并带单位后缀，开关即拨，文本输入定宽。
      脏状态逐行可见（琥珀点），底部操作条显示「已修改 N 项」；保存成功按钮短暂切换为「已保存」回执。
      入场沿用全站 CSS fade-up；数据到达后的行级错落、额度条展开、保存回执、校验失败抖动、版本刷新淡入
      由 GSAP 驱动，并整体尊重 prefers-reduced-motion。
      普通用户仅渲染「账户」组，无系统参数/系统信息权限。
    -->

    <!-- ===== 组一：账户（所有角色） ===== -->
    <section class="min-w-0" aria-labelledby="settings-hd-account">
      <div class="mb-3 flex items-center gap-2">
        <h2 id="settings-hd-account" class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">账户</h2>
        <span class="h-px flex-1 bg-ink/10" aria-hidden="true"></span>
        <span class="text-xs text-ink-muted">所有角色</span>
      </div>

      <div class="flex flex-col gap-4 sm:gap-5">
        <!-- 账户信息（只读）：身份区 + 三列体征，明卡 -->
        <div class="dash-card fade-up p-4 sm:p-5" role="region" aria-label="账户信息">
          <!-- 加载骨架：与「身份区 + 三列体征」的最终几何同构 -->
          <div v-if="meLoading" class="flex flex-col gap-5 xl:flex-row xl:items-center">
            <div class="flex shrink-0 items-center gap-3.5">
              <div class="h-12 w-12 rounded-full bg-ink/5 animate-pulse" />
              <div class="space-y-2">
                <div class="h-4 w-24 rounded bg-ink/5 animate-pulse" />
                <div class="h-3 w-14 rounded bg-ink/5 animate-pulse" />
              </div>
            </div>
            <div class="grid flex-1 gap-4 sm:grid-cols-3 xl:border-l xl:border-ink/5 xl:pl-6">
              <div v-for="i in 3" :key="i" class="space-y-2">
                <div class="h-2.5 w-14 rounded bg-ink/5 animate-pulse" />
                <div class="h-4 w-24 rounded bg-ink/5 animate-pulse" />
              </div>
            </div>
          </div>

          <div v-else class="flex flex-col gap-5 xl:flex-row xl:items-center">
            <!-- 身份区：首字头像 + 用户名 + 角色徽标（与侧边栏用户区同源视觉） -->
            <div class="flex shrink-0 items-center gap-3.5">
              <span
                class="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-brand/15 text-lg font-semibold text-brand ring-1 ring-brand/20"
              >{{ (meInfo?.username || 'U').charAt(0).toUpperCase() }}</span>
              <div class="min-w-0">
                <p class="truncate text-base font-semibold text-ink">{{ meInfo?.username || '-' }}</p>
                <span class="mt-1 inline-flex items-center rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-medium text-brand">
                  {{ meRoleLabel }}
                </span>
              </div>
            </div>

            <!-- 体征区：定义列表语义；xl 起与身份区同行、细线分界，与全站 uppercase 小标签同款 -->
            <dl class="grid flex-1 gap-x-6 gap-y-4 sm:grid-cols-3 xl:border-l xl:border-ink/5 xl:pl-6">
              <div>
                <dt class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">注册时间</dt>
                <dd class="mt-1 text-sm font-semibold tabular-nums text-ink">{{ meInfo?.createdAt || '-' }}</dd>
              </div>
              <div>
                <dt class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">最近登录</dt>
                <dd class="mt-1 text-sm font-semibold tabular-nums text-ink">{{ meInfo?.lastLogin || '-' }}</dd>
              </div>
              <div>
                <dt class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">额度使用</dt>
                <dd class="mt-1 text-sm font-semibold tabular-nums text-ink">
                  {{ meInfo?.quota?.used ?? '-' }}
                  <span class="text-xs font-normal text-ink-muted">/ {{ meInfo?.quota?.limit ?? '-' }} 个平台账号</span>
                </dd>
                <!-- 语义色：<80% 品牌蓝、≥80% 琥珀预警（对齐 quota_warn_ratio 默认阈值）、满额危险红；展开由 GSAP 驱动 -->
                <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-ink/10">
                  <div
                    ref="quotaBarRef"
                    class="h-full origin-left rounded-full"
                    :class="quotaBarCls"
                    :style="{ width: quotaPct + '%' }"
                  />
                </div>
              </div>
            </dl>
          </div>
        </div>

        <!-- 修改密码：图标章组头与系统参数组同构，三字段一行排开，动作右置 -->
        <form ref="pwdCardRef" class="dash-card fade-up delay-1 p-4 sm:p-5" @submit.prevent="onChangePassword">
          <div class="mb-3 flex items-center gap-2.5">
            <span class="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand" aria-hidden="true">
              <Icon name="lock" :size="15" />
            </span>
            <div class="min-w-0">
              <p class="text-sm font-semibold text-ink">修改密码</p>
              <p class="text-xs text-ink-muted">定期更换密码可提升账号安全</p>
            </div>
          </div>

          <div class="grid gap-3 sm:grid-cols-3">
            <div>
              <label class="mb-1 block text-xs font-medium text-ink-muted" for="pwd-old">原密码</label>
              <input
                id="pwd-old"
                v-model="pwdForm.old"
                type="password"
                autocomplete="current-password"
                placeholder="输入当前密码"
                class="login-input px-3 py-2.5 text-sm"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-ink-muted" for="pwd-next">新密码</label>
              <input
                id="pwd-next"
                v-model="pwdForm.next"
                type="password"
                autocomplete="new-password"
                :placeholder="pwdMinHint"
                class="login-input px-3 py-2.5 text-sm"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-ink-muted" for="pwd-confirm">确认新密码</label>
              <input
                id="pwd-confirm"
                v-model="pwdForm.confirm"
                type="password"
                autocomplete="new-password"
                placeholder="再次输入新密码"
                class="login-input px-3 py-2.5 text-sm"
                :class="confirmError && 'border-danger focus:border-danger focus:ring-danger/10'"
              />
              <p v-if="confirmError" class="mt-1 text-xs text-danger">{{ confirmError }}</p>
            </div>
          </div>

          <div class="mt-3 flex justify-end border-t border-ink/5 pt-3">
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

    <!-- ===== 组二：系统（仅管理员） ===== -->
    <section v-if="auth.isAdmin" class="min-w-0" aria-labelledby="settings-hd-system">
      <div class="mb-3 flex items-center gap-2">
        <h2 id="settings-hd-system" class="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">系统</h2>
        <span class="h-px flex-1 bg-ink/10" aria-hidden="true"></span>
        <span class="text-xs text-ink-muted">仅管理员</span>
      </div>

      <div class="flex flex-col gap-4 sm:gap-5">
        <!-- 系统信息：横向深墨蓝状态横幅——身份色签名块，与账户信息横幅同构 -->
        <div
          role="region"
          aria-label="系统信息"
          class="fade-up delay-2 flex flex-col gap-5 rounded-2xl bg-ink p-5 ring-1 ring-white/10 shadow-[0_1px_2px_rgba(20,33,61,0.04),0_18px_40px_-20px_rgba(20,33,61,0.45)] lg:flex-row lg:items-center"
        >
          <!-- 加载骨架：与「版本主值区 + 三列体征」的最终几何同构 -->
          <div v-if="infoLoading" class="flex flex-1 flex-col gap-5 lg:flex-row lg:items-center">
            <div class="shrink-0 space-y-2.5">
              <div class="h-2.5 w-16 rounded bg-white/15 animate-pulse" />
              <div class="h-7 w-32 rounded bg-white/15 animate-pulse" />
              <div class="h-6 w-24 rounded-full bg-white/10 animate-pulse" />
            </div>
            <div class="grid flex-1 gap-4 sm:grid-cols-3 lg:border-l lg:border-white/10 lg:pl-6">
              <div v-for="i in 3" :key="i" class="space-y-2">
                <div class="h-2.5 w-14 rounded bg-white/15 animate-pulse" />
                <div class="h-4 w-20 rounded bg-white/15 animate-pulse" />
              </div>
            </div>
          </div>

          <template v-else>
            <!-- 版本是唯一主值：等宽字体强化工程感；刷新就近放在版本标签旁 -->
            <div class="shrink-0">
              <div class="flex items-center gap-3">
                <p class="text-[11px] font-semibold uppercase tracking-wider text-white/50">系统版本</p>
                <button
                  type="button"
                  class="inline-flex items-center gap-1 text-xs font-medium text-white/60 transition hover:text-white"
                  @click="loadSystemInfo"
                >
                  <Icon name="refresh" :size="13" :class="infoLoading && 'animate-spin'" />
                  刷新
                </button>
              </div>
              <p ref="versionRef" class="mt-2 font-mono text-[26px] font-semibold leading-none tracking-tight text-white">v{{ sysInfo?.version ?? '-' }}</p>
              <span class="mt-3 inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium text-white/85 ring-1 ring-white/20">
                <span class="h-1.5 w-1.5 rounded-full" :class="envDotCls"></span>
                {{ envLabel }}
              </span>
            </div>

            <!-- 体征三列：细线与版本块分界，语义与账户信息横幅一致 -->
            <dl class="grid flex-1 gap-x-6 gap-y-4 sm:grid-cols-3 lg:border-l lg:border-white/10 lg:pl-6">
              <div>
                <dt class="text-[11px] font-semibold uppercase tracking-wider text-white/50">数据库</dt>
                <dd class="mt-1 flex items-center gap-2 text-sm font-semibold tabular-nums text-white">
                  <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="dbOk ? 'bg-success brand-dot' : 'bg-danger'"></span>
                  {{ dbOk ? '连接正常' : '连接异常' }}
                </dd>
              </div>
              <div>
                <dt class="text-[11px] font-semibold uppercase tracking-wider text-white/50">已运行时长</dt>
                <dd class="mt-1 text-sm font-semibold tabular-nums text-white">{{ uptimeLabel }}</dd>
                <p v-if="startedAtLabel" class="mt-0.5 text-xs text-white/45">{{ startedAtLabel }}</p>
              </div>
              <div>
                <dt class="text-[11px] font-semibold uppercase tracking-wider text-white/50">用户规模</dt>
                <dd class="mt-1 text-sm font-semibold tabular-nums text-white">{{ usersTotal }} 人</dd>
                <p class="mt-0.5 text-xs text-white/45">管理员 {{ sysInfo?.users?.admins ?? '-' }} · 用户 {{ sysInfo?.users?.users ?? '-' }}</p>
              </div>
            </dl>
          </template>
        </div>

        <!-- 系统参数：卡内按业务语义二次分组，短组 xl 双列、长文本组通栏 -->
        <div ref="paramCardRef" class="dash-card fade-up delay-3 p-4 sm:p-5" role="region" aria-label="系统参数">
          <p class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">系统参数</p>

          <!-- 加载骨架：与分组参数行的最终几何同构 -->
          <div v-if="settingsLoading" class="grid gap-x-10 md:grid-cols-2">
            <div v-for="i in 6" :key="i" class="flex items-center justify-between gap-4 py-3.5">
              <div class="space-y-1.5">
                <div class="h-3.5 w-28 rounded bg-ink/5 animate-pulse" />
                <div class="h-3 w-44 rounded bg-ink/5 animate-pulse" />
              </div>
              <div class="h-8 w-20 rounded-lg bg-ink/5 animate-pulse" />
            </div>
          </div>

          <template v-else>
            <!-- 短组（每组 ≤2 行）：xl 双列并排；长文本组通栏，描述不受窄列挤压 -->
            <div class="grid gap-x-10 gap-y-5 xl:grid-cols-2">
              <section v-for="group in shortGroups" :key="group.id" :aria-labelledby="'param-g-' + group.id" class="min-w-0">
                <div class="flex items-center gap-2.5">
                  <span class="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand" aria-hidden="true">
                    <Icon :name="group.icon" :size="15" />
                  </span>
                  <div class="min-w-0">
                    <p :id="'param-g-' + group.id" class="text-sm font-semibold leading-tight text-ink">{{ group.title }}</p>
                    <p class="mt-0.5 truncate text-xs text-ink-muted">{{ group.hint }}</p>
                  </div>
                </div>

                <div class="mt-1">
                  <div
                    v-for="item in group.items"
                    :key="item.key"
                    class="param-row flex items-center justify-between gap-4 py-2.5"
                  >
                    <div class="min-w-0">
                      <label :for="'param-' + item.key" class="flex items-center gap-1.5 text-sm font-medium text-ink">
                        {{ item.label }}
                        <span
                          v-if="isDirty(item)"
                          class="h-1.5 w-1.5 shrink-0 rounded-full bg-amber"
                          aria-hidden="true"
                          title="已修改，待保存"
                        ></span>
                        <span v-if="item.type === 'int'" class="text-[11px] font-normal tabular-nums text-ink/40">
                          {{ item.min }} ~ {{ item.max }}
                        </span>
                      </label>
                      <p class="mt-0.5 text-xs leading-relaxed text-ink-muted">{{ item.desc }}</p>
                    </div>

                    <ConfigToggle
                      v-if="item.type === 'bool'"
                      :id="'param-' + item.key"
                      v-model="form[item.key]"
                      class="shrink-0"
                    />
                    <input
                      v-else-if="item.type === 'str'"
                      :id="'param-' + item.key"
                      v-model.trim="form[item.key]"
                      type="text"
                      autocomplete="off"
                      class="login-input w-full max-w-[240px] shrink-0 px-3 py-2 text-sm"
                      placeholder="未配置"
                    />
                    <div v-else class="relative shrink-0">
                      <input
                        :id="'param-' + item.key"
                        v-model.number="form[item.key]"
                        type="number"
                        :min="item.min"
                        :max="item.max"
                        class="login-input w-32 px-3 py-2 pr-10 text-right text-sm tabular-nums"
                      />
                      <span class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-ink-muted">
                        {{ paramUnits[item.key] || '' }}
                      </span>
                    </div>
                  </div>
                </div>
              </section>
            </div>

            <!-- 通栏组：地图服务及未归类的兜底参数 -->
            <div
              v-for="group in fullGroups"
              :key="group.id"
              class="mt-5 border-t border-ink/5 pt-4"
              :aria-labelledby="'param-g-' + group.id"
            >
              <div class="flex items-center gap-2.5">
                <span class="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand" aria-hidden="true">
                  <Icon :name="group.icon" :size="15" />
                </span>
                <div class="min-w-0">
                  <p :id="'param-g-' + group.id" class="text-sm font-semibold leading-tight text-ink">{{ group.title }}</p>
                  <p class="mt-0.5 text-xs text-ink-muted">{{ group.hint }}</p>
                </div>
              </div>

              <div
                v-for="item in group.items"
                :key="item.key"
                class="param-row mt-1 flex flex-col gap-2 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
              >
                <div class="min-w-0">
                  <label :for="'param-' + item.key" class="flex items-center gap-1.5 text-sm font-medium text-ink">
                    {{ item.label }}
                    <span
                      v-if="isDirty(item)"
                      class="h-1.5 w-1.5 shrink-0 rounded-full bg-amber"
                      aria-hidden="true"
                      title="已修改，待保存"
                    ></span>
                  </label>
                  <p class="mt-0.5 text-xs leading-relaxed text-ink-muted">{{ item.desc }}</p>
                </div>
                <input
                  :id="'param-' + item.key"
                  v-model.trim="form[item.key]"
                  type="text"
                  autocomplete="off"
                  class="login-input w-full max-w-[320px] shrink-0 px-3 py-2 text-sm"
                  placeholder="未配置"
                />
              </div>
            </div>

            <!-- 底部操作区：脏计数徽标 + 恢复默认值靠左，保存按钮靠右 -->
            <div class="mt-4 flex flex-wrap items-center gap-3 border-t border-ink/5 pt-3">
              <span
                v-if="changedCount"
                class="inline-flex items-center gap-1.5 rounded-full bg-warning-soft px-2.5 py-1 text-xs font-medium text-warning"
              >
                <span class="h-1.5 w-1.5 rounded-full bg-warning" aria-hidden="true"></span>
                已修改 {{ changedCount }} 项
              </span>
              <button
                v-if="changedCount"
                type="button"
                class="text-xs font-medium text-ink-muted transition hover:text-ink"
                @click="resetFormToDefaults"
              >
                恢复默认值
              </button>
              <button
                ref="saveBtnRef"
                type="button"
                :disabled="saving || !changedCount"
                class="ml-auto inline-flex items-center gap-1.5 rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-70"
                @click="onSaveSettings"
              >
                <Icon v-if="savedFlash" name="check" :size="15" />
                {{ savedFlash ? '已保存' : saving ? '保存中…' : '保存设置' }}
              </button>
            </div>
          </template>
        </div>
      </div>
    </section>

    <!-- 底部间距占位：真实在流子元素，盒高计入 scrollHeight，不受滚动容器末端 padding/margin 折叠影响；
         -mt-5 抵消根容器 gap-5，确保底部间距精确 24px、与其它页面一致 -->
    <div class="h-6 shrink-0 -mt-5" aria-hidden="true"></div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'
import ConfigToggle from '@/components/signconfig/ConfigToggle.vue'
import * as authApi from '@/api/auth'
import { fetchAccountInfo } from '@/api/me'
import { getSettings, updateSettings, getSystemInfo } from '@/api/settings'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'

const auth = useAuthStore()

// 细节动效统一开关：系统级减弱动效偏好下，GSAP 全部短路，直接呈现最终状态
const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches

// ==================== 区一：修改密码 ====================
const pwdForm = reactive({ old: '', next: '', confirm: '' })
const pwdSubmitting = ref(false)
const confirmError = ref('')
const pwdCardRef = ref(null)
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
  } catch {
    /* 失败已由 request.js 全局 toast 提示 */
  } finally {
    pwdSubmitting.value = false
  }
}

// 校验失败抖动：动效回应操作结果，指向出错位置而不是只靠文案
watch(confirmError, (msg) => {
  if (!msg || REDUCED_MOTION || !pwdCardRef.value) return
  gsap.to(pwdCardRef.value, {
    keyframes: { x: [-5, 5, -3, 3, 0] },
    duration: 0.32,
    ease: 'power2.out',
    clearProps: 'x',
  })
})

// ==================== 区二：账户信息（所有角色，只读） ====================
const meInfo = ref(null)
const meLoading = ref(false)
const meRoleLabel = computed(() => (meInfo.value?.role === 'admin' ? '管理员' : '普通用户'))
// 进度条宽度钳制在 0~100，防止后端异常值把轨道撑破
const quotaPct = computed(() => Math.min(100, Math.max(0, Number(meInfo.value?.quota?.pct ?? 0))))
// 额度进度条语义色：<80% 品牌蓝、≥80% 琥珀预警（对齐系统参数 quota_warn_ratio 默认阈值）、满额危险红
const quotaBarCls = computed(() => {
  if (quotaPct.value >= 100) return 'bg-danger'
  if (quotaPct.value >= 80) return 'bg-amber'
  return 'bg-brand'
})
const quotaBarRef = ref(null)

// 额度条数据到达后从 0 展开（scaleX 动画不与 width 绑定冲突），动画结束清内联变换交还响应式
watch(quotaPct, () => {
  if (REDUCED_MOTION || !quotaBarRef.value) return
  gsap.fromTo(
    quotaBarRef.value,
    { scaleX: 0 },
    { scaleX: 1, duration: 0.7, ease: 'power3.out', clearProps: 'transform' }
  )
})

async function loadAccountInfo() {
  meLoading.value = true
  try {
    meInfo.value = await fetchAccountInfo()
  } catch {
    /* 失败已由 request.js 全局 toast 提示；体征位以「-」占位 */
  } finally {
    meLoading.value = false
  }
}

// ==================== 区三：系统参数（仅管理员） ====================
const settingsItems = ref([])
const form = reactive({})
const defaultsSnapshot = reactive({})
const settingsLoading = ref(false)
const saving = ref(false)
const paramCardRef = ref(null)
const saveBtnRef = ref(null)
const savedFlash = ref(false)
let savedFlashTimer = null

// 分组目录：系统参数按业务语义二次归类，key → 组映射；后端新增键未收录时兜底进「其他参数」
const PARAM_GROUPS = [
  { id: 'register', title: '注册与额度', icon: 'user-check', hint: '新账号的开通方式与用量基线', keys: ['registration_enabled', 'default_quota'] },
  { id: 'security', title: '账号安全', icon: 'shield', hint: '密码策略与会话凭证有效期', keys: ['password_min_length', 'session_hours'] },
  { id: 'data', title: '数据治理', icon: 'layers', hint: '日志清理周期与预警口径', keys: ['sign_log_retention_days', 'quota_warn_ratio'] },
  { id: 'map', title: '地图服务', icon: 'map-pin', hint: '位置池「地图拾取」的高德开放平台凭证', keys: ['amap_web_key', 'amap_security_code'], full: true },
]
// 数字参数的单位后缀：随输入框内联展示，免去逐项把单位写进 label
const PARAM_UNITS = {
  default_quota: '个',
  password_min_length: '位',
  session_hours: '小时',
  sign_log_retention_days: '天',
  quota_warn_ratio: '%',
}

const paramUnits = PARAM_UNITS

const paramGroups = computed(() => {
  const byKey = Object.fromEntries(settingsItems.value.map((it) => [it.key, it]))
  const used = new Set()
  const groups = []
  for (const g of PARAM_GROUPS) {
    const items = g.keys.filter((k) => byKey[k]).map((k) => {
      used.add(k)
      return byKey[k]
    })
    if (items.length) groups.push({ ...g, items })
  }
  const rest = settingsItems.value.filter((it) => !used.has(it.key))
  if (rest.length) {
    groups.push({ id: 'other', title: '其他参数', icon: 'sliders', hint: '未归类的系统配置', items: rest, full: true })
  }
  return groups
})

const shortGroups = computed(() => paramGroups.value.filter((g) => !g.full))
const fullGroups = computed(() => paramGroups.value.filter((g) => g.full))

function isDirty(item) {
  return form[item.key] !== undefined && form[item.key] !== item.current
}

const changedCount = computed(() => settingsItems.value.filter((it) => isDirty(it)).length)

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
  } catch {
    /* 失败已由 request.js 全局 toast 提示 */
  } finally {
    settingsLoading.value = false
  }
}

// 参数行数据到达后的错落入场：仅在首次加载完成时触发一次
watch(settingsLoading, async (loading) => {
  if (loading || REDUCED_MOTION || !settingsItems.value.length) return
  await nextTick()
  const rows = paramCardRef.value?.querySelectorAll('.param-row')
  if (rows?.length) {
    gsap.fromTo(
      rows,
      { opacity: 0, y: 6 },
      { opacity: 1, y: 0, duration: 0.32, ease: 'power2.out', stagger: 0.02, clearProps: 'opacity,transform' }
    )
  }
})

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
    // 保存回执：按钮短暂切换为「已保存」，配合轻脉冲明确"这次点击生效了"
    savedFlash.value = true
    clearTimeout(savedFlashTimer)
    savedFlashTimer = setTimeout(() => {
      savedFlash.value = false
    }, 1600)
  } catch {
    /* 失败已由 request.js 全局 toast 提示 */
  } finally {
    saving.value = false
  }
}

watch(savedFlash, (on) => {
  if (!on || REDUCED_MOTION || !saveBtnRef.value) return
  gsap.fromTo(
    saveBtnRef.value,
    { scale: 0.95 },
    { scale: 1, duration: 0.35, ease: 'back.out(2)', clearProps: 'transform' }
  )
})

// ==================== 区四：系统信息（仅管理员） ====================
const sysInfo = ref(null)
const infoLoading = ref(false)
const versionRef = ref(null)

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
  } catch {
    /* 失败已由 request.js 全局 toast 提示 */
  } finally {
    infoLoading.value = false
  }
}

// 版本号刷新（首次加载或手动刷新）时轻淡入，提示"这是最新读数"
watch(
  () => sysInfo.value?.version,
  async () => {
    if (REDUCED_MOTION || !versionRef.value) return
    await nextTick()
    gsap.fromTo(
      versionRef.value,
      { opacity: 0, y: 4 },
      { opacity: 1, y: 0, duration: 0.4, ease: 'power2.out', clearProps: 'opacity,transform' }
    )
  }
)

onMounted(() => {
  // 账户信息/账户安全对所有角色可用；系统参数/系统信息仅管理员加载（后端同样做了 admin 校验）
  loadAccountInfo()
  if (auth.isAdmin) {
    loadSettings()
    loadSystemInfo()
  }
})

onBeforeUnmount(() => {
  clearTimeout(savedFlashTimer)
})
</script>
