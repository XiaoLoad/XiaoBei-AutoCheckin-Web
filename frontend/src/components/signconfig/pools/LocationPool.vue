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

    <div class="flex items-center justify-between">
      <p class="text-xs text-ink-muted">
        {{ scope === 'system' ? '平台预设位置（管理员维护，普通用户可选不可改）' : '我的位置（本人可添加）' }}
      </p>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
        :disabled="!canEdit"
        @click="openAdd"
      >
        <Icon name="plus" :size="15" />添加位置
      </button>
    </div>

    <!-- 内联表单 -->
    <div v-if="editing" class="rounded-xl border border-brand/20 bg-brand/5 p-3">
      <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <input v-model="form.name" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="名称（须与地址对应）" />
        <input v-model="form.address" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="地址（第三方接口固定参数）" />
        <input v-model="form.lat" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="纬度" />
        <input v-model="form.lng" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="经度" />
        <input v-model="form.offset" type="number" class="rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10" placeholder="坐标偏移（米）" />
      </div>
      <div class="mt-2 flex justify-end gap-2">
        <button class="rounded-lg border border-ink/10 px-3 py-1.5 text-sm text-ink-soft hover:bg-cloud" @click="editing = null">取消</button>
        <button class="rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark" :disabled="!form.name" @click="save">保存</button>
      </div>
    </div>

    <!-- 列表 -->
    <div class="overflow-hidden rounded-xl border border-ink/10">
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
          <tr v-if="list.length === 0"><td colspan="4" class="px-3 py-8 text-center text-ink-muted">暂无位置</td></tr>
          <tr v-for="loc in list" :key="loc.id" class="border-t border-ink/5">
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
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import Icon from '@/components/Icon.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { useAuthStore } from '@/store/modules/auth'

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

const editing = ref(null)
const form = reactive({ id: '', name: '', address: '', lat: '', lng: '', offset: '' })

const list = computed(() => (scope.value === 'system' ? store.systemLocations : store.userLocations))

function openAdd() {
  form.id = ''
  form.name = ''
  form.address = ''
  form.lat = ''
  form.lng = ''
  form.offset = ''
  editing.value = 'add'
}
function openEdit(loc) {
  form.id = loc.id
  form.name = loc.name
  form.address = loc.address
  form.lat = loc.lat
  form.lng = loc.lng
  form.offset = loc.offset
  editing.value = 'edit'
}
async function save() {
  await store.saveLocation({
    scope: scope.value,
    id: form.id || undefined,
    name: form.name,
    address: form.address,
    lat: Number(form.lat) || 0,
    lng: Number(form.lng) || 0,
    offset: Number(form.offset) || 0
  })
  editing.value = null
}
function del(loc) {
  store.deleteLocation({ scope: scope.value, id: loc.id })
}
</script>
