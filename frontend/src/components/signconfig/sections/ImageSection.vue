<template>
  <ConfigSection title="图片策略" icon="image" :source="source">
    <div class="space-y-3">
      <div class="flex items-center justify-between gap-3">
        <div>
          <p class="text-sm font-medium text-ink">上传图片</p>
          <p class="text-xs text-ink-muted">开启后签到时按策略消费图库图片</p>
        </div>
        <ConfigToggle v-model="config.image.enabled" />
      </div>

      <GCollapse :show="config.image.enabled">
        <div class="space-y-3 pt-1">
          <!-- 01 取图范围：选什么就用什么，选中项直接决定下方内容，不是换个标签继续选 -->
          <div>
            <div class="mb-1.5 flex items-center gap-1.5">
              <span class="text-[11px] font-medium tabular-nums text-ink-muted">01</span>
              <span class="text-xs font-medium text-ink">图从哪来</span>
              <span class="ml-auto text-[11px] text-ink-muted">定范围</span>
            </div>
            <div class="inline-flex w-full rounded-lg bg-cloud p-0.5" role="group" aria-label="取图方式">
              <button
                v-for="m in modeOptions"
                :key="m.value"
                type="button"
                class="flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition"
                :class="config.image.mode === m.value ? 'bg-elevated text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
                :aria-pressed="config.image.mode === m.value"
                @click="config.image.mode = m.value"
              >
                {{ m.label }}
              </button>
            </div>

            <!-- key 触发整块重建：切换取图方式时条件块重播入场，而不是原地换文案 -->
            <div :key="config.image.mode" class="xb-block-in mt-2.5">
              <LibraryPicker
                v-if="!isByGroup"
                v-model="config.image.groupId"
                :options="groupOptions"
                :images="previewImages"
              />
              <GroupScope
                v-else
                :config="config.image"
                :audit="audit"
                :account="account"
                :group-options="groupOptions"
                :fallback-images="previewImages"
                :is-admin="isAdmin"
                @bind="router.push('/group-push')"
              />
            </div>

            <!-- 账号视角：配置套不知道账号，只有这里能给出「算到本账号是什么」 -->
            <ResolvedScope
              v-if="account && isByGroup"
              class="mt-2.5"
              :resolved="resolved"
              :account-name="account.name"
              :group-kind="kind"
            />

            <!-- 漏网时才给就地兜底：分组绑好了就不该再摆选择器，否则又被读成「选了分组还能再选」 -->
            <div v-if="accountGap" class="xb-block-in mt-2.5 flex items-center gap-2">
              <span class="flex-none text-xs text-ink-muted">兜底</span>
              <div class="min-w-0 flex-1">
                <LibraryPicker
                  v-model="config.image.groupId"
                  tone="fallback"
                  :options="groupOptions"
                  :images="previewImages"
                />
              </div>
            </div>
          </div>

          <!-- 02 用完去哪 -->
          <div>
            <div class="mb-1.5 flex items-center gap-1.5">
              <span class="text-[11px] font-medium tabular-nums text-ink-muted">02</span>
              <span class="text-xs font-medium text-ink">用完去哪</span>
              <span class="ml-auto text-[11px] text-ink-muted">定去向</span>
            </div>
            <div class="inline-flex w-full rounded-lg bg-cloud p-0.5" role="group" aria-label="图片策略">
              <button
                v-for="s in strategyOptions"
                :key="s.value"
                type="button"
                class="flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition"
                :class="config.image.strategy === s.value ? 'bg-elevated text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
                :aria-pressed="config.image.strategy === s.value"
                @click="config.image.strategy = s.value"
              >
                {{ s.label }}
              </button>
            </div>
            <p class="mt-1.5 text-xs text-ink-muted">{{ strategyHint }}</p>
          </div>

          <div class="flex flex-wrap items-center gap-2 border-t border-ink/5 pt-2.5">
            <span class="text-xs text-ink-muted">图库 {{ activeCount }} 张（回收站 {{ trashCount }} 张）</span>
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-lg border border-ink/10 px-3 py-1.5 text-sm text-ink-soft transition hover:bg-cloud"
              @click="store.gotoResource('images')"
            >
              <Icon name="image" :size="14" />管理图库
            </button>
          </div>
        </div>
      </GCollapse>
    </div>
  </ConfigSection>
</template>

<script setup>
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import ConfigToggle from '@/components/signconfig/ConfigToggle.vue'
import GCollapse from '@/components/signconfig/GCollapse.vue'
import Icon from '@/components/Icon.vue'
import LibraryPicker from '@/components/signconfig/sections/image/LibraryPicker.vue'
import GroupScope from '@/components/signconfig/sections/image/GroupScope.vue'
import ResolvedScope from '@/components/signconfig/sections/image/ResolvedScope.vue'
import { useAuthStore } from '@/stores/auth'
import { useSignConfigStore } from '@/stores/signConfig'
import { fetchGroups, fetchMembers } from '@/api/groupPush'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' },
  // 账号上下文：传入时本卡改为「账号视角」，额外给出这条规则算到该账号的实际取图结果。
  // 配置套编辑器与定时任务抽屉不传，保持模板视角。
  account: { type: Object, default: null }
})

const store = useSignConfigStore()
const auth = useAuthStore()
const router = useRouter()
const isAdmin = computed(() => auth.isAdmin)

const modeOptions = [
  { label: '固定图库', value: 'fixed' },
  { label: '按分组取图', value: 'byGroup' }
]
// 分段控件容不下长句，选项只留短语，后果由下方一行随选中项说明
const strategyOptions = [
  { label: '循环复用', value: 'recycle' },
  { label: '用后删除', value: 'delete' },
  { label: '入回收站', value: 'trash' }
]
const strategyHints = {
  recycle: '用完放回图库，之后仍会被抽中',
  delete: '用完直接删除，不可恢复',
  trash: '用完移入回收站，可手动恢复；超 7 天自动清理'
}

const isByGroup = computed(() => props.config.image.mode === 'byGroup')
const kind = computed(() => (props.config.image.groupKind === 'class' ? 'class' : 'dorm'))
const strategyHint = computed(() => strategyHints[props.config.image.strategy] || '')

// ''/null 均表示不过滤分组（全部图库），与后端 config.image.groupId 口径一致
const scopeId = computed(() => {
  const v = props.config.image.groupId
  return v === '' || v == null ? null : String(v)
})

// 可抽张数：recycle 会把范围内的 used 整批放回 active，故 active 与 used 都算；
// trash/delete 不回池，used 属历史残留，不再参与抽取（与 image_store 的认领口径对齐）
function poolOf(gid) {
  const key = gid === '' || gid == null ? null : String(gid)
  const recycle = props.config.image.strategy === 'recycle'
  return store.imageLibrary.filter((i) => {
    if (i.inTrash) return false
    if (key !== null && String(i.groupId) !== key) return false
    return recycle || !i.used
  })
}

const previewImages = computed(() => poolOf(scopeId.value))
const groupOptions = computed(() => [
  { label: '全部图库', value: '' },
  ...store.imageGroups.map((g) => ({ label: g.name, value: g.id }))
])
const activeCount = computed(() => store.imageLibrary.filter((i) => !i.inTrash).length)
const trashCount = computed(() => store.imageLibrary.filter((i) => i.inTrash).length)

// ── 分组健康度核对：漏网的分组/账号都会落到兜底图库，配置时必须看得见 ──
const enabledAccounts = computed(() => store.accounts.filter((a) => a.status !== 'disabled'))
const audit = ref(null)
const auditReady = ref(false)
const groupRows = ref([])
// Map<string(groupId), Set<string(accountId)>>，仅寝室分组需要
const memberIndex = ref(null)

let auditToken = 0
function resetAudit() {
  auditToken += 1 // 在途响应立即失效，避免切回固定图库后旧核对结果回填
  audit.value = null
  auditReady.value = false
  groupRows.value = []
  memberIndex.value = null
}

function buildAudit(rows, index, k) {
  const accs = enabledAccounts.value
  const unboundGroups = rows.filter((g) => !g.imageGroupId).length
  let unboundAccounts
  if (k === 'class') {
    // 班级分组由账号 className 实时派生，故「未分组」实质是 className 为空的账号
    const names = new Set(rows.map((g) => (g.name || '').trim()))
    unboundAccounts = accs.filter((a) => {
      const cls = (a.className || '').trim()
      return !cls || !names.has(cls)
    }).length
  } else {
    const covered = new Set()
    if (index) for (const set of index.values()) for (const id of set) covered.add(id)
    unboundAccounts = accs.filter((a) => !covered.has(String(a.id))).length
  }
  return { total: rows.length, unboundGroups, unboundAccounts }
}

async function loadAudit() {
  if (isAdmin.value || !props.config.image.enabled || !isByGroup.value) {
    resetAudit()
    return
  }
  const k = kind.value
  const token = ++auditToken
  try {
    const rows = await fetchGroups(k)
    if (token !== auditToken) return
    let index = null
    if (k === 'dorm') {
      // 寝室成员只能逐组取；分组通常在个位数，一次并发拉完后本地建索引，
      // 健康度统计与账号解析共用这一份，不再二次请求
      const lists = await Promise.all(rows.map((g) => fetchMembers(g.id).catch(() => [])))
      if (token !== auditToken) return
      index = new Map(rows.map((g, i) => [String(g.id), new Set(lists[i].map((m) => String(m.accountId)))]))
    }
    groupRows.value = rows
    memberIndex.value = index
    audit.value = buildAudit(rows, index, k)
    auditReady.value = true
  } catch (e) {
    if (token !== auditToken) return
    audit.value = null
    auditReady.value = false
    groupRows.value = []
    memberIndex.value = null
  }
}

// 账号实际取图结果。口径与后端 _account_group_image_id 对齐：分组绑定的图库必须仍存在，
// 悬空视为未绑；未绑或账号无归属时逐级回退配置套的 groupId，再回退全部图库。
const resolved = computed(() => {
  const acc = props.account
  if (!acc || !isByGroup.value || !auditReady.value) return null
  const fallbackId = scopeId.value
  const infoOf = (gid) => {
    const g = gid == null ? null : store.imageGroups.find((x) => String(x.id) === String(gid))
    return g ? { imageName: g.name, count: poolOf(gid).length } : { imageName: '全部图库', count: poolOf(null).length }
  }
  const boundImage = (gid) => (gid && store.imageGroups.some((x) => String(x.id) === String(gid)) ? gid : null)
  // 兜底图库是否真的配了：没配时后端一路退到全部图库，结论文案要跟着换口径
  const fallbackSet = !!boundImage(fallbackId)

  let row = null
  if (kind.value === 'class') {
    const cls = (acc.className || '').trim()
    row = cls ? groupRows.value.find((g) => (g.name || '').trim() === cls) || null : null
  } else {
    row = groupRows.value.find((g) => memberIndex.value?.get(String(g.id))?.has(String(acc.id))) || null
  }
  if (!row) return { groupName: '', ...infoOf(fallbackId), reason: 'no-group', fallbackSet }
  const hit = boundImage(row.imageGroupId)
  if (!hit) return { groupName: row.name, ...infoOf(fallbackId), reason: 'unbound-group', fallbackSet }
  return { groupName: row.name, ...infoOf(hit), reason: '', fallbackSet }
})

// 账号视角的就地兜底只在漏网时给：本账号有正常归属时不摆选择器。
// 兜底值仍是本配置的 image.groupId，改这里等于给这个任务实例预设兜底。
const accountGap = computed(() => !!resolved.value?.reason)

onMounted(loadAudit)

// 本页在 keep-alive 内，去「分组」页绑完图库再回来不会重新挂载，
// 靠 onActivated 重核对一次，否则健康度与账号解析结果还停在离开前的状态
onActivated(() => {
  if (isByGroup.value && props.config.image.enabled) loadAudit()
})

// 与 script setup 末尾约定一致：watch 写在最后，避免 setup 阶段 TDZ
watch(
  [() => props.config.image.mode, () => props.config.image.groupKind, () => props.config.image.enabled],
  loadAudit
)
</script>
