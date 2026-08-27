<template>
  <div class="space-y-3">
    <div v-if="showSwitcher" class="inline-flex rounded-xl bg-cloud p-1 text-sm">
      <button
        v-for="s in scopes"
        :key="s.value"
        type="button"
        class="rounded-lg px-3 py-1.5 font-medium transition"
        :class="scope === s.value ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
        @click="scope = s.value"
      >
        {{ s.label }}
      </button>
    </div>

    <!-- 顶部：搜索 + 添加 -->
    <div class="flex flex-wrap items-center gap-2">
      <div class="relative min-w-[200px] flex-1">
        <Icon name="search" :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
        <input
          v-model="query"
          type="text"
          class="w-full rounded-xl border border-ink/10 bg-white py-2 pl-9 pr-3 text-sm text-ink outline-none focus:outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
          placeholder="搜索名称或地址"
          @input="onQuery"
        />
      </div>
      <button
        type="button"
        class="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-brand px-3 py-2 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
        :disabled="!canEdit || showModal"
        @click="openAdd"
      >
        <Icon name="plus" :size="15" />添加位置
      </button>
    </div>

    <p class="text-xs text-ink-muted">
      {{ scope === 'system' ? '平台预设位置（管理员维护，普通用户可选不可改）' : '我的位置（本人可添加）' }}
    </p>

    <!-- 列表 -->
    <div v-if="filtered.length === 0" class="py-8 text-center text-sm text-ink-muted">
      {{ query ? '未找到匹配的位置' : '暂无位置' }}
    </div>
    <div v-else class="overflow-hidden rounded-xl border border-ink/10">
      <table class="w-full text-left text-sm">
        <thead class="bg-cloud/60 text-ink-muted">
          <tr>
            <th class="px-3 py-2 font-medium">名称</th>
            <th class="px-3 py-2 font-medium">经纬度</th>
            <th class="px-3 py-2 font-medium">偏移</th>
            <th class="px-3 py-2 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="loc in paged" :key="loc.id" class="border-t border-ink/5 hover:bg-cloud/40">
            <td class="px-3 py-2"><p class="font-medium text-ink">{{ loc.name }}</p><p class="truncate text-xs text-ink-muted">{{ loc.address }}</p></td>
            <td class="px-3 py-2 tabular-nums text-ink-soft">{{ loc.lat }}, {{ loc.lng }}</td>
            <td class="px-3 py-2 tabular-nums text-ink-soft">{{ loc.offset }} 米</td>
            <td class="px-3 py-2 text-right">
              <button v-if="canEdit" class="text-xs text-brand hover:underline" @click="openEdit(loc)">编辑</button>
              <button v-if="canEdit" class="ml-3 text-xs text-danger hover:underline" @click="del(loc)">删除</button>
              <span v-else class="text-xs text-ink-muted">只读</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页（复用 BasePagination） -->
    <BasePagination
      v-if="filtered.length"
      :page="page"
      :page-size="pageSize"
      :total="filtered.length"
      @update:page="page = $event"
      @update:page-size="onSize"
    />

    <!-- 添加 / 编辑 模态框 -->
    <BaseModal v-model="showModal" :title="editingId ? '编辑位置' : '添加位置'">
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div class="sm:col-span-2">
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">名称</label>
          <input v-model="form.name" class="w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="对此位置的描述，如：3栋502寝室" />
        </div>
        <div class="sm:col-span-2">
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">地址</label>
          <input v-model="form.address" class="w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="第三方接口定位所需的地址参数（必填）" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">纬度</label>
          <input v-model="form.lat" class="w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="纬度（必填）" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">经度</label>
          <input v-model="form.lng" class="w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="经度（必填）" />
        </div>
        <div class="sm:col-span-2">
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">坐标偏移（米，默认 10）</label>
          <input v-model="form.offset" type="number" class="w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="坐标偏移（米，默认 10）" />
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
          :disabled="!form.name || !form.address || !form.lat || !form.lng || saving"
          @click="save"
        >
          {{ saving ? '保存中…' : '保存' }}
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

const props = defineProps({
  // 外部锁定作用域：传入后隐藏切换器并固定为该系统/用户池（用于「系统资源」只显示系统池、「我的资源」只显示我的池）
  fixedScope: { type: String, default: '' }
})

const store = useSignConfigStore()
const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

const scopes = [
  { value: 'system', label: '平台预设位置' },
  { value: 'user', label: '我的位置' }
]
const scope = ref(props.fixedScope || (isAdmin.value ? 'system' : 'user'))
const showSwitcher = computed(() => !props.fixedScope)
const canEdit = computed(() => (scope.value === 'system' ? isAdmin.value : true))

const list = computed(() => (scope.value === 'system' ? store.systemLocations : store.userLocations))

// 模糊搜索（名称或地址，不区分大小写）
const query = ref('')
const page = ref(1)
const pageSize = ref(10)

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return list.value
  return list.value.filter((l) => l.name.toLowerCase().includes(q) || (l.address || '').toLowerCase().includes(q))
})
const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

// 切换作用域 / 搜索词 / 每页条数变化后，重置或回拉页码
watch(scope, () => {
  query.value = ''
  page.value = 1
})
watch([filtered, pageSize], () => {
  const tp = Math.max(1, Math.ceil(filtered.value.length / pageSize.value))
  if (page.value > tp) page.value = tp
})
function onQuery() {
  page.value = 1
}
function onSize(s) {
  pageSize.value = Number(s)
}

// 模态框：添加 / 编辑
const showModal = ref(false)
const editingId = ref('')
const saving = ref(false)
const form = reactive({ name: '', address: '', lat: '', lng: '', offset: '' })

function openAdd() {
  editingId.value = ''
  form.name = ''
  form.address = ''
  form.lat = ''
  form.lng = ''
  form.offset = 10
  showModal.value = true
}
function openEdit(loc) {
  editingId.value = loc.id
  form.name = loc.name
  form.address = loc.address
  form.lat = loc.lat
  form.lng = loc.lng
  form.offset = loc.offset
  showModal.value = true
}
async function save() {
  if (!form.name) return
  saving.value = true
  try {
    await store.saveLocation({
      scope: scope.value,
      id: editingId.value || undefined,
      name: form.name,
      address: form.address,
      lat: Number(form.lat) || 0,
      lng: Number(form.lng) || 0,
      offset: Number(form.offset) || 10
    })
    showModal.value = false
  } finally {
    saving.value = false
  }
}
function del(loc) {
  store.deleteLocation({ scope: scope.value, id: loc.id })
}
</script>
