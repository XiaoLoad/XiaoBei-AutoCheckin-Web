<template>
  <div class="flex flex-col gap-6 lg:flex-1 lg:min-h-0">
    <!-- 页头 -->
    <div class="dash-card fade-up shrink-0 p-4 sm:p-5">
      <div class="flex items-start justify-between gap-4">
        <div>
          <h1 class="text-lg font-semibold text-ink">群推送</h1>
          <p class="mt-1 text-sm text-ink-muted">
            把同一批人的当日签到结果合并成一条消息，推送到对应的 QQ 群——而非每人各发一条。
          </p>
        </div>
        <span class="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-brand/10 px-3 py-1 text-xs font-medium text-brand">
          <Icon name="send" :size="14" />合并推送
        </span>
      </div>

      <!-- 分组切换 -->
      <div class="mt-4 inline-flex rounded-xl bg-cloud/60 p-1">
        <button
          v-for="t in tabs"
          :key="t.key"
          type="button"
          class="rounded-lg px-4 py-1.5 text-sm font-medium transition"
          :class="activeTab === t.key ? 'bg-elevated text-ink shadow-sm' : 'text-ink-muted hover:text-ink'"
          @click="activeTab = t.key"
        >
          {{ t.label }}
        </button>
      </div>
    </div>

    <!-- 班级分组 -->
    <div v-if="activeTab === 'class'" class="dash-card fade-up flex flex-col overflow-hidden rounded-2xl lg:flex-1 lg:min-h-0">
      <div class="flex items-center gap-2 px-4 pt-4 text-xs text-ink-muted">
        <Icon name="info" :size="14" />
        <span>班级分组按账号的「班级」字段自动归类，无需手动维护成员；填好 QQ 群编码后即可推送。</span>
      </div>

      <div v-if="loading" class="flex flex-1 items-center justify-center py-10 text-sm text-ink-muted">加载中…</div>
      <div v-else-if="classGroups.length === 0" class="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-10 text-center text-sm text-ink-muted">
        <Icon name="members" :size="28" class="opacity-50" />
        <span>暂无班级信息：账号校验通过后会自动带回班级字段。</span>
      </div>
      <div v-else class="xb-scroll flex-1 overflow-auto p-4 lg:min-h-0">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <article
            v-for="g in classGroups"
            :key="g.name"
            v-reveal
            class="flex flex-col rounded-xl border border-ink/10 bg-card p-4 transition hover:border-brand/40"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-ink">{{ g.name }}</p>
                <p class="mt-0.5 text-xs text-ink-muted">{{ g.memberCount }} 名成员</p>
              </div>
              <StatusBadge :today="g.today" />
            </div>

            <div class="mt-3 border-t border-ink/5 pt-3">
              <label class="mb-1 block text-xs text-ink-muted">QQ 群编码（qq_code）</label>
              <div class="flex items-center gap-2">
                <input
                  v-model="g._qq"
                  type="text"
                  placeholder="未绑定，填后推送"
                  class="login-input w-full py-1.5 text-sm"
                />
                <button
                  type="button"
                  class="shrink-0 rounded-lg border border-ink/10 px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:bg-cloud"
                  :disabled="savingClass === g.name"
                  @click="saveClass(g)"
                >
                  {{ savingClass === g.name ? '保存中' : '保存' }}
                </button>
              </div>
            </div>
          </article>
        </div>
      </div>
    </div>

    <!-- 寝室分组 -->
    <div v-else class="flex flex-col gap-3 lg:flex-1 lg:min-h-0">
      <div class="dash-card fade-up flex shrink-0 flex-wrap items-center gap-2 p-3 sm:p-4">
        <span class="text-sm font-medium text-ink-soft">寝室分组</span>
        <span class="text-xs text-ink-muted">手动建组、手动维护成员；未绑 QQ 群不推送。</span>
        <button
          type="button"
          class="ml-auto inline-flex items-center justify-center gap-1.5 rounded-xl bg-brand px-3.5 py-2 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark"
          @click="openCreate"
        >
          <Icon name="plus" :size="17" />新建分组
        </button>
      </div>

      <div class="dash-card fade-up flex flex-col overflow-hidden rounded-2xl lg:flex-1 lg:min-h-0">
        <div v-if="loading" class="flex flex-1 items-center justify-center py-10 text-sm text-ink-muted">加载中…</div>
        <div v-else-if="dormGroups.length === 0" class="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-10 text-center text-sm text-ink-muted">
          <Icon name="box" :size="28" class="opacity-50" />
          <span>还没有寝室分组，点击「新建分组」把同寝室账号归到一起。</span>
        </div>
        <div v-else class="xb-scroll flex-1 overflow-auto p-4 lg:min-h-0">
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <article
              v-for="g in dormGroups"
              :key="g.id"
              v-reveal
              class="flex flex-col rounded-xl border border-ink/10 bg-card p-4 transition hover:border-brand/40"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <p class="truncate text-sm font-medium text-ink">{{ g.name }}</p>
                  <p class="mt-0.5 text-xs text-ink-muted">{{ g.memberCount }} 名成员</p>
                </div>
                <StatusBadge :today="g.today" />
              </div>

              <div class="mt-3 border-t border-ink/5 pt-3">
                <label class="mb-1 block text-xs text-ink-muted">QQ 群编码（qq_code）</label>
                <div class="flex items-center gap-2">
                  <input
                    v-model="g._qq"
                    type="text"
                    placeholder="未绑定，填后推送"
                    class="login-input w-full py-1.5 text-sm"
                  />
                  <button
                    type="button"
                    class="shrink-0 rounded-lg border border-ink/10 px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:bg-cloud"
                    :disabled="savingDorm === g.id"
                    @click="saveDorm(g)"
                  >
                    {{ savingDorm === g.id ? '保存中' : '保存' }}
                  </button>
                </div>
              </div>

              <div class="mt-3 flex items-center justify-end gap-1 border-t border-ink/5 pt-2.5">
                <button class="rounded-lg px-2.5 py-1.5 text-xs font-medium text-brand transition hover:bg-brand/10" @click="openMembers(g)">成员</button>
                <button class="rounded-lg px-2.5 py-1.5 text-xs font-medium text-ink-muted transition hover:bg-cloud" :disabled="flushing === g.id" @click="flush(g)">
                  {{ flushing === g.id ? '发送中' : '立即发送' }}
                </button>
                <button class="rounded-lg px-2.5 py-1.5 text-xs font-medium text-danger transition hover:bg-danger/10" @click="askDelete(g)">删除</button>
              </div>
            </article>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建寝室分组弹窗 -->
    <BaseModal v-model="createOpen" title="新建寝室分组" size="md">
      <div class="space-y-4">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">分组名称</label>
          <input v-model="createForm.name" type="text" placeholder="如：3栋507" class="login-input w-full py-2 text-sm" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">QQ 群编码（qq_code）<span class="text-ink-muted">（可选）</span></label>
          <input v-model="createForm.qqCode" type="text" placeholder="留空可稍后绑定" class="login-input w-full py-2 text-sm" />
          <p class="mt-1.5 text-xs text-ink-muted">未绑定 QQ 群前不会推送；可在卡片上随时编辑。</p>
        </div>
      </div>
      <template #footer>
        <button type="button" class="flex-1 rounded-xl border border-ink/10 py-2.5 text-sm font-medium text-ink-soft transition hover:bg-cloud" @click="createOpen = false">取消</button>
        <button type="button" class="flex-1 rounded-xl bg-brand py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:opacity-60" :disabled="!createForm.name.trim() || creating" @click="submitCreate">
          {{ creating ? '创建中' : '创建' }}
        </button>
      </template>
    </BaseModal>

    <!-- 成员管理弹窗 -->
    <BaseModal v-model="membersOpen" :title="membersTitle" size="2xl">
      <div v-if="membersLoading" class="py-8 text-center text-sm text-ink-muted">加载中…</div>
      <template v-else>
        <!-- 当前成员 -->
        <div class="mb-4">
          <p class="mb-2 text-xs font-medium text-ink-muted">当前成员（{{ memberRows.length }}）</p>
          <div v-if="memberRows.length === 0" class="rounded-xl border border-dashed border-ink/10 px-3 py-6 text-center text-sm text-ink-muted">
            暂无成员，从下方添加。
          </div>
          <div v-else class="space-y-1.5">
            <div
              v-for="m in memberRows"
              :key="m.accountId"
              class="flex items-center justify-between gap-2 rounded-lg border border-ink/5 bg-cloud/40 px-3 py-2"
            >
              <div class="min-w-0">
                <p class="truncate text-sm text-ink">{{ m.name || m.account }}</p>
                <p class="truncate text-xs text-ink-muted">{{ m.account }} · {{ m.className || '—' }}</p>
              </div>
              <button class="shrink-0 rounded-lg px-2.5 py-1 text-xs font-medium text-danger transition hover:bg-danger/10" @click="removeMemberFromGroup(m.accountId)">移除</button>
            </div>
          </div>
        </div>

        <!-- 添加成员 -->
        <div>
          <p class="mb-2 text-xs font-medium text-ink-muted">添加账号</p>
          <div class="relative mb-2 w-full sm:w-72">
            <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
            <input v-model="memberKeyword" type="text" placeholder="搜索账号 / 姓名" class="login-input py-2 pl-9 text-sm" />
          </div>
          <div class="xb-scroll max-h-60 overflow-auto rounded-xl border border-ink/5">
            <label
              v-for="a in filteredAccounts"
              :key="a.id"
              class="flex cursor-pointer items-center gap-3 border-b border-ink/5 px-3 py-2.5 transition hover:bg-cloud/50"
            >
              <BaseCheckbox :model-value="selectedAccountIds.includes(a.id)" @update:model-value="toggleSelect(a.id, $event)" />
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm text-ink">{{ (a.profile && a.profile.name) || '未命名' }}</p>
                <p class="truncate text-xs text-ink-muted">{{ a.account }} · {{ (a.profile && a.profile.className) || '—' }}</p>
              </div>
            </label>
            <div v-if="filteredAccounts.length === 0" class="px-3 py-6 text-center text-sm text-ink-muted">无匹配账号</div>
          </div>
        </div>
      </template>
      <template #footer>
        <button type="button" class="flex-1 rounded-xl border border-ink/10 py-2.5 text-sm font-medium text-ink-soft transition hover:bg-cloud" @click="membersOpen = false">关闭</button>
        <button type="button" class="flex-1 rounded-xl bg-brand py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:opacity-60" :disabled="selectedAccountIds.length === 0 || addingMembers" @click="submitAddMembers">
          {{ addingMembers ? '添加中' : `添加 ${selectedAccountIds.length} 人` }}
        </button>
      </template>
    </BaseModal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import Icon from '@/components/Icon.vue'
import BaseModal from '@/components/BaseModal.vue'
import BaseCheckbox from '@/components/BaseCheckbox.vue'
import { toast } from '@/utils/toast'
import {
  fetchGroups, createDormGroup, updateDormGroup, deleteDormGroup,
  fetchMembers, addMembers, removeMember, bindClassGroup, flushGroup
} from '@/api/groupPush'
import { fetchAccounts } from '@/api/accounts'

const tabs = [
  { key: 'class', label: '班级分组' },
  { key: 'dorm', label: '寝室分组' }
]
const activeTab = ref('class')

const loading = ref(false)
const classGroups = ref([])
const dormGroups = ref([])
const savingClass = ref('')
const savingDorm = ref(null)
const flushing = ref(null)

// 新建分组弹窗
const createOpen = ref(false)
const creating = ref(false)
const createForm = ref({ name: '', qqCode: '' })

// 成员管理弹窗
const membersOpen = ref(false)
const membersLoading = ref(false)
const memberRows = ref([])
const currentGroup = ref(null)
const memberKeyword = ref('')
const selectedAccountIds = ref([])
const addingMembers = ref(false)
const allAccounts = ref([])

const membersTitle = computed(() => `成员管理 · ${currentGroup.value ? currentGroup.value.name : ''}`)

const filteredAccounts = computed(() => {
  const kw = memberKeyword.value.trim().toLowerCase()
  const memberIds = new Set(memberRows.value.map((m) => m.accountId))
  return allAccounts.value.filter((a) => !memberIds.has(a.id)).filter((a) => {
    if (!kw) return true
    const name = (a.profile && a.profile.name) || ''
    return a.account.toLowerCase().includes(kw) || name.toLowerCase().includes(kw)
  })
})

async function loadAll() {
  loading.value = true
  try {
    const [cls, dorm] = await Promise.all([
      fetchGroups('class'),
      fetchGroups('dorm')
    ])
    classGroups.value = cls.map((g) => ({ ...g, _qq: g.qqCode }))
    dormGroups.value = dorm.map((g) => ({ ...g, _qq: g.qqCode }))
  } catch (e) {
    // 错误已由拦截器 toast
  } finally {
    loading.value = false
  }
}

async function saveClass(g) {
  savingClass.value = g.name
  try {
    await bindClassGroup({ name: g.name, qqCode: g._qq.trim() })
    toast('已保存', 'success')
    await loadAll()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    savingClass.value = ''
  }
}

async function saveDorm(g) {
  savingDorm.value = g.id
  try {
    await updateDormGroup(g.id, { qqCode: g._qq.trim() })
    toast('已保存', 'success')
    await loadAll()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    savingDorm.value = ''
  }
}

async function flush(g) {
  flushing.value = g.id
  try {
    const res = await flushGroup({ type: g.type, id: g.id, name: g.name })
    const t = res && res.today
    toast(t ? `已发送（${statusText(t.status)}）` : '已触发发送', 'success')
    await loadAll()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    flushing.value = ''
  }
}

function statusText(s) {
  return { success: '全部已签', partial: '部分已签', fail: '发送失败' }[s] || s
}

function openCreate() {
  createForm.value = { name: '', qqCode: '' }
  createOpen.value = true
}

async function submitCreate() {
  creating.value = true
  try {
    await createDormGroup({ name: createForm.value.name.trim(), qqCode: createForm.value.qqCode.trim() })
    toast('分组已创建', 'success')
    createOpen.value = false
    await loadAll()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    creating.value = false
  }
}

function askDelete(g) {
  if (!window.confirm(`确定删除寝室分组「${g.name}」？成员关系将一并清除。`)) return
  deleteDormGroup(g.id).then(() => {
    toast('已删除', 'success')
    loadAll()
  }).catch(() => {})
}

async function openMembers(g) {
  currentGroup.value = g
  membersOpen.value = true
  memberKeyword.value = ''
  selectedAccountIds.value = []
  membersLoading.value = true
  try {
    const [rows, accounts] = await Promise.all([
      fetchMembers(g.id),
      fetchAccounts()
    ])
    memberRows.value = rows
    allAccounts.value = accounts
  } catch (e) {
    /* toast by interceptor */
  } finally {
    membersLoading.value = false
  }
}

function toggleSelect(id, checked) {
  if (checked) {
    if (!selectedAccountIds.value.includes(id)) selectedAccountIds.value = [...selectedAccountIds.value, id]
  } else {
    selectedAccountIds.value = selectedAccountIds.value.filter((x) => x !== id)
  }
}

async function removeMemberFromGroup(id) {
  try {
    await removeMember(currentGroup.value.id, id)
    memberRows.value = memberRows.value.filter((m) => m.accountId !== id)
    await loadAll()
  } catch (e) {
    /* toast by interceptor */
  }
}

async function submitAddMembers() {
  addingMembers.value = true
  try {
    const ids = selectedAccountIds.value
    const res = await addMembers(currentGroup.value.id, ids)
    toast(`已添加 ${res && res.added != null ? res.added : ids.length} 人`, 'success')
    selectedAccountIds.value = []
    await openMembers(currentGroup.value)
    await loadAll()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    addingMembers.value = false
  }
}

// 切换 tab 时仅在首次需要补拉对应数据（两个 tab 的数据都在 loadAll 中一次取齐）
onMounted(loadAll)
</script>
