<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <p class="text-xs text-ink-muted">
      系统级 UA 模板（机型默认值），由管理员维护；普通用户在「高级设置」中下拉选择，亦可自定义填写。
    </p>

    <!-- 顶部工具栏：搜索 + 添加 -->
    <div class="shrink-0 flex flex-wrap items-center gap-2">
      <div class="relative min-w-[200px] flex-1">
        <Icon name="search" :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
        <input
          v-model="query"
          type="text"
          class="w-full rounded-xl border border-ink/10 bg-elevated py-2 pl-9 pr-3 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
          placeholder="搜索机型名称"
          @input="onQuery"
        />
      </div>
      <button
        v-if="isAdmin"
        type="button"
        class="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-brand px-3 py-2 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
        :disabled="showModal"
        @click="openAdd"
      >
        <Icon name="plus" :size="15" />添加模板
      </button>
    </div>

    <!-- 批量操作条（仅管理员，有选中时显示） -->
    <div v-if="isAdmin && selectedIds.length" class="shrink-0 flex items-center justify-between rounded-xl bg-brand/5 px-3 py-2 text-sm">
      <span class="text-ink-soft">已选 {{ selectedIds.length }} 项</span>
      <div class="flex items-center gap-2">
        <button class="rounded-lg border border-ink/10 px-3 py-1 text-ink-soft transition hover:bg-cloud" @click="clearSelection">取消选择</button>
        <button
          class="inline-flex items-center gap-1.5 rounded-lg bg-danger px-3 py-1 font-medium text-white transition hover:bg-danger/90 disabled:opacity-50"
          :disabled="saving"
          @click="batchDelete"
        >
          <Icon name="trash" :size="14" />批量删除
        </button>
      </div>
    </div>

    <!-- 空态 -->
    <div v-if="paged.length === 0" class="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-ink/10 py-10 text-center text-sm text-ink-muted">
      {{ query ? '未找到匹配的机型模板' : '暂无模板' }}
    </div>

    <!-- 列表：flex-1 min-h-0 吸收剩余高度，溢出时内部滚动，避免撑破宿主卡片背景 -->
    <div v-else class="min-h-0 flex-1 overflow-auto rounded-xl border border-ink/10">
      <table class="w-full text-left text-sm">
        <thead class="bg-cloud/60 text-ink-muted">
          <tr>
            <th v-if="isAdmin" class="w-10 px-3 py-2">
              <input
                type="checkbox"
                class="h-4 w-4 cursor-pointer accent-brand"
                :checked="allOnPageSelected"
                @change="toggleAllOnPage"
              />
            </th>
            <th class="px-3 py-2 font-medium">机型名称</th>
            <th class="px-3 py-2 font-medium">User-Agent</th>
            <th v-if="isAdmin" class="px-3 py-2 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="u in paged"
            :key="u.id"
            class="border-t border-ink/5 transition"
            :class="selectedIds.includes(u.id) ? 'bg-brand/5' : 'hover:bg-cloud/40'"
          >
            <td v-if="isAdmin" class="px-3 py-2">
              <input
                type="checkbox"
                class="h-4 w-4 cursor-pointer accent-brand"
                :checked="selectedIds.includes(u.id)"
                @change="toggle(u.id)"
              />
            </td>
            <td class="px-3 py-2 font-medium text-ink">{{ u.name }}</td>
            <td class="px-3 py-2">
              <p class="max-w-md truncate text-xs text-ink-muted" :title="u.ua">{{ u.ua }}</p>
            </td>
            <td v-if="isAdmin" class="px-3 py-2 text-right">
              <button class="text-xs text-brand hover:underline" @click="openEdit(u)">编辑</button>
              <button class="ml-3 text-xs text-brand hover:underline" @click="openDerive(u)">派生</button>
              <button class="ml-3 text-xs text-danger hover:underline" @click="del(u)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页（复用 BasePagination） -->
    <BasePagination
      v-if="filtered.length"
      class="shrink-0"
      :page="page"
      :page-size="pageSize"
      :total="filtered.length"
      @update:page="page = $event"
      @update:page-size="onSize"
    />

    <!-- 添加 / 编辑 模态框 -->
    <BaseModal v-model="showModal" :title="editingId ? '编辑 UA 模板' : '添加 UA 模板'">
      <div class="space-y-3">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">机型名称</label>
          <input
            v-model="form.name"
            class="w-full rounded-xl border border-ink/10 bg-elevated px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
            placeholder="模板名称（如 iPhone 15）"
          />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">User-Agent</label>
          <textarea
            v-model="form.ua"
            rows="3"
            class="w-full resize-y rounded-xl border border-ink/10 bg-elevated px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
            placeholder="User-Agent 字符串"
          />
        </div>
      </div>
      <template #footer>
        <button
          type="button"
          class="flex-1 rounded-xl border border-ink/10 px-4 py-2.5 text-sm font-medium text-ink-soft transition hover:bg-cloud"
          @click="showModal = false"
        >
          取消
        </button>
        <button
          type="button"
          class="flex-1 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-70"
          :disabled="!form.name || !form.ua || saving"
          @click="save"
        >
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </template>
    </BaseModal>

    <!-- 批量派生模态框：同机型不同系统/WebView 版本，扩充机型池规模 -->
    <BaseModal v-model="showDeriveModal" title="批量派生 UA 变体">
      <div class="space-y-3">
        <p class="text-xs leading-relaxed text-ink-muted">
          以「{{ deriveTarget?.name || '' }}」为基准，生成同机型、不同
          Android/iOS 系统版本与 WebView 版本的变体（机型型号保持不变）。
          变体自动启用并加入机型池，用于机型池分配模式下扩充池规模、
          让更多账号各得一台"设备"。生成确定性：同一模板重复派生结果一致，已存在的变体自动跳过。
        </p>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">派生数量（1~12）</label>
          <input
            v-model.number="deriveCount"
            type="number"
            min="1"
            max="12"
            class="w-32 rounded-xl border border-ink/10 bg-elevated px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
          />
        </div>
      </div>
      <template #footer>
        <button
          type="button"
          class="flex-1 rounded-xl border border-ink/10 px-4 py-2.5 text-sm font-medium text-ink-soft transition hover:bg-cloud"
          @click="showDeriveModal = false"
        >
          取消
        </button>
        <button
          type="button"
          class="flex-1 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-70"
          :disabled="saving || !(deriveCount >= 1 && deriveCount <= 12)"
          @click="doDerive"
        >
          {{ saving ? '派生中…' : '开始派生' }}
        </button>
      </template>
    </BaseModal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import Icon from '@/components/Icon.vue'
import BasePagination from '@/components/BasePagination.vue'
import BaseModal from '@/components/BaseModal.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'

const store = useSignConfigStore()
const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

// 模糊搜索（按机型名称，不区分大小写）
const query = ref('')
const page = ref(1)
const pageSize = ref(10)
const selectedIds = ref([])

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return store.uaTemplates
  return store.uaTemplates.filter((u) => u.name.toLowerCase().includes(q))
})

// 搜索词或每页条数变化后，页码越界则回拉
watch([filtered, pageSize], () => {
  const tp = Math.max(1, Math.ceil(filtered.value.length / pageSize.value))
  if (page.value > tp) page.value = tp
})
function onQuery() {
  page.value = 1
  clearSelection()
}
function onSize(s) {
  pageSize.value = Number(s)
}

const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

// 批量选择
function toggle(id) {
  const i = selectedIds.value.indexOf(id)
  if (i === -1) selectedIds.value.push(id)
  else selectedIds.value.splice(i, 1)
}
function toggleAllOnPage(e) {
  const ids = paged.value.map((u) => u.id)
  if (e.target.checked) {
    for (const id of ids) if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
  } else {
    selectedIds.value = selectedIds.value.filter((id) => !ids.includes(id))
  }
}
const allOnPageSelected = computed(
  () => paged.value.length > 0 && paged.value.every((u) => selectedIds.value.includes(u.id))
)
function clearSelection() {
  selectedIds.value = []
}
async function batchDelete() {
  if (!selectedIds.value.length) return
  await store.deleteUaTemplates(selectedIds.value)
  clearSelection()
}

// 模态框：添加 / 编辑
const showModal = ref(false)
const editingId = ref('')
const saving = ref(false)
const form = reactive({ name: '', ua: '' })

function openAdd() {
  editingId.value = ''
  form.name = ''
  form.ua = ''
  showModal.value = true
}
function openEdit(u) {
  editingId.value = u.id
  form.name = u.name
  form.ua = u.ua
  showModal.value = true
}
async function save() {
  if (!form.name || !form.ua) return
  saving.value = true
  try {
    await store.saveUaTemplate({ id: editingId.value || undefined, name: form.name, ua: form.ua })
    showModal.value = false
  } finally {
    saving.value = false
  }
}
function del(u) {
  store.deleteUaTemplate(u.id)
}

// 批量派生：以选中模板为基准生成同机型变体
const showDeriveModal = ref(false)
const deriveTarget = ref(null)
const deriveCount = ref(6)
function openDerive(u) {
  deriveTarget.value = u
  deriveCount.value = 6
  showDeriveModal.value = true
}
async function doDerive() {
  if (!deriveTarget.value) return
  saving.value = true
  try {
    const { added, skipped } = await store.deriveUaVariants(deriveTarget.value.id, deriveCount.value)
    showDeriveModal.value = false
    if (added) toast(`派生完成：新增 ${added} 条变体` + (skipped ? `，跳过重复 ${skipped} 条` : ''), 'success')
    else toast('没有新增变体（全部与池内已有条目重复）', 'info')
  } finally {
    saving.value = false
  }
}
</script>
