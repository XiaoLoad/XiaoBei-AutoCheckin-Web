<template>
  <!-- 弹性列撑满宿主卡片：网格区吸收剩余高度，分页固定在卡片底部（避免大面积留白） -->
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <div v-if="showSwitcher" class="inline-flex shrink-0 self-start rounded-xl bg-cloud p-1 text-sm">
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
          class="w-full rounded-xl border border-ink/10 bg-white py-2 pl-9 pr-3 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
          placeholder="搜索名称或地址"
          @input="onQuery"
        />
      </div>
      <button
        type="button"
        class="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-brand px-3 py-2 text-sm font-medium text-white shadow-lg shadow-brand/20 transition hover:bg-brand-dark disabled:opacity-50"
        :disabled="!canEdit || showModal"
        @click="openAdd"
      >
        <Icon name="plus" :size="15" />添加位置
      </button>
    </div>

    <!-- 列表：网格区吸收剩余高度（内容顶部对齐），分页固定卡片底部 -->
    <div v-if="filtered.length === 0" class="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-ink/10 text-ink-muted">
      <Icon name="map-pin" :size="30" class="opacity-40" />
      <p class="text-sm">{{ query ? '未找到匹配的位置' : '暂无位置' }}</p>
    </div>
    <TransitionGroup v-else tag="div" class="grid flex-1 grid-cols-1 content-start gap-2.5 sm:grid-cols-2 xl:grid-cols-3" name="loc-list">
      <article
        v-for="loc in paged"
        :key="loc.id"
        class="loc-card group relative overflow-hidden rounded-xl border border-ink/10 bg-white p-3.5 transition duration-300 hover:-translate-y-0.5 hover:border-brand/30 hover:shadow-md hover:shadow-ink/5"
      >
        <div class="flex items-start gap-2.5">
          <span
            class="grid h-9 w-9 shrink-0 place-items-center rounded-lg"
            :class="scope === 'system' ? 'bg-info/10 text-info' : 'bg-brand/10 text-brand'"
          >
            <Icon name="map-pin" :size="16" />
          </span>
          <div class="min-w-0 flex-1 pr-16">
            <div class="flex items-center gap-1.5">
              <p class="min-w-0 flex-1 truncate text-sm font-semibold text-ink" :title="loc.name">{{ loc.name }}</p>
              <span
                v-if="scope === 'system'"
                class="shrink-0 rounded-full bg-info/10 px-1.5 py-0.5 text-[10px] font-medium text-info"
              >预设</span>
            </div>
            <p class="mt-0.5 truncate text-xs text-ink-muted" :title="loc.address">{{ loc.address || '—' }}</p>
          </div>
        </div>

        <div class="mt-2.5 flex flex-wrap items-center gap-1.5 text-[11px] tabular-nums text-ink-muted">
          <span class="rounded bg-cloud/80 px-1.5 py-0.5" :title="`${loc.lat}, ${loc.lng}`">{{ loc.lat }}, {{ loc.lng }}</span>
          <span class="rounded bg-cloud/80 px-1.5 py-0.5">偏移 {{ loc.offset }} 米</span>
        </div>

        <!-- 操作：悬停浮现（触屏常显） -->
        <div
          v-if="canEdit"
          class="absolute right-2.5 top-2.5 z-10 flex gap-1 opacity-100 transition group-hover:opacity-100 sm:opacity-0 sm:group-hover:opacity-100"
        >
          <button
            type="button"
            class="grid h-7 w-7 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud hover:text-brand"
            title="编辑"
            @click="openEdit(loc)"
          >
            <Icon name="edit" :size="13" />
          </button>
          <button
            type="button"
            class="grid h-7 w-7 place-items-center rounded-lg text-ink-muted transition hover:bg-danger/10 hover:text-danger"
            title="删除"
            @click="del(loc)"
          >
            <Icon name="trash" :size="13" />
          </button>
        </div>
        <span v-else class="absolute right-2.5 top-2.5 z-10 rounded-full bg-cloud/80 px-1.5 py-0.5 text-[10px] text-ink-muted">只读</span>

        <!-- 删除二次确认（行内展开，避免误删） -->
        <div v-if="confirmingId === loc.id" class="mt-2.5 flex items-center justify-end gap-1.5 border-t border-ink/5 pt-2">
          <span class="mr-auto text-[11px] text-danger">确认删除「{{ loc.name }}」？</span>
          <button type="button" class="rounded-lg px-2 py-1 text-xs font-medium text-ink-muted transition hover:bg-cloud" @click="confirmingId = null">取消</button>
          <button
            type="button"
            class="rounded-lg bg-danger px-2.5 py-1 text-xs font-medium text-white transition hover:bg-danger/90"
            @click="confirmDel(loc)"
          >确认</button>
        </div>
      </article>
    </TransitionGroup>

    <!-- 分页（复用 BasePagination，固定卡片底部） -->
    <BasePagination
      v-if="filtered.length"
      class="shrink-0"
      :page="page"
      :page-size="pageSize"
      :total="filtered.length"
      @update:page="page = $event"
      @update:page-size="onSize"
    />

    <!-- 添加 / 编辑 模态框：地图拾取（高德） / 手动输入 双模式 -->
    <BaseModal v-model="showModal" :title="editingId ? '编辑位置' : '添加位置'" :size="pickerMode === 'map' ? '2xl' : 'md'">
      <!-- 名称（两模式共用）：地图拾取会把识别到的地址回填到这里，用户可编辑 -->
      <div class="mb-3">
        <label class="mb-1.5 block text-sm font-medium text-ink-soft">名称 <span class="text-red-500">*</span></label>
        <input v-model="form.name" class="login-input" placeholder="对此位置的描述，如：3栋502寝室" @input="onNameInput" />
      </div>

      <!-- 模式切换 -->
      <div class="mb-3 grid grid-cols-2 gap-2">
        <button
          type="button"
          class="rounded-xl border px-3 py-2 text-sm font-medium transition"
          :class="pickerMode === 'map' ? 'border-brand bg-brand/5 text-brand shadow-sm' : 'border-ink/10 text-ink-soft hover:bg-cloud'"
          @click="pickerMode = 'map'"
        >
          地图拾取
        </button>
        <button
          type="button"
          class="rounded-xl border px-3 py-2 text-sm font-medium transition"
          :class="pickerMode === 'manual' ? 'border-brand bg-brand/5 text-brand shadow-sm' : 'border-ink/10 text-ink-soft hover:bg-cloud'"
          @click="pickerMode = 'manual'"
        >
          手动输入
        </button>
      </div>

      <!-- 地图拾取：搜索/点击落点 + 逆地理编码（回填到名称）；地址号为学校签到必填参数 -->
      <div v-if="pickerMode === 'map'" class="mb-3">
        <AmapPicker
          :model-value="pickedPoint"
          height="320px"
          @update:model-value="onPointPicked"
          @unavailable="pickerMode = 'manual'"
        />
        <div class="mt-3">
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">
            地址号 <span class="text-red-500">*</span>
            <span class="font-normal text-ink-muted">（学校签到所需参数）</span>
          </label>
          <input v-model="form.address" class="login-input" placeholder="如：1388号" />
        </div>
        <div class="mt-2.5 flex items-center gap-1.5 rounded-lg bg-cloud/70 px-2.5 py-1.5 text-xs">
          <span class="shrink-0 rounded bg-white px-1.5 py-0.5 tabular-nums text-ink-soft">
            {{ pickedPoint ? `${pickedPoint.lng}, ${pickedPoint.lat}` : '—, —' }}
          </span>
          <span v-if="!pickedPoint" class="text-warning">请先在地图上拾取位置（点击地图或搜索地点）</span>
        </div>
      </div>

      <!-- 手动输入：地址号 + 经纬度 -->
      <div v-else class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div class="sm:col-span-2">
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">
            地址号 <span class="text-red-500">*</span>
            <span class="font-normal text-ink-muted">（学校签到所需参数）</span>
          </label>
          <input v-model="form.address" class="login-input" placeholder="如：1388号" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">纬度 <span class="text-red-500">*</span></label>
          <input v-model="form.lat" class="login-input" placeholder="纬度（必填）" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">经度 <span class="text-red-500">*</span></label>
          <input v-model="form.lng" class="login-input" placeholder="经度（必填）" />
        </div>
      </div>

      <!-- 坐标偏移（两模式共用） -->
      <div class="mt-3">
        <label class="mb-1.5 block text-sm font-medium text-ink-soft">坐标偏移（米）</label>
        <input v-model="form.offset" type="number" class="login-input" placeholder="默认 10" />
        <p class="mt-1.5 text-xs text-ink-muted">提交签到时在配置坐标周围随机偏移该距离，模拟真实 GPS 抖动。</p>
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
          :disabled="!canSave || saving"
          @click="save"
        >
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </template>
    </BaseModal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { gsap } from 'gsap'
import Icon from '@/components/Icon.vue'
import BasePagination from '@/components/BasePagination.vue'
import BaseModal from '@/components/BaseModal.vue'
import AmapPicker from '@/components/common/AmapPicker.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
  // 外部锁定作用域：传入后隐藏切换器并固定为该系统/用户池（用于「系统资源」只显示系统池、「我的资源」只显示我的池）
  fixedScope: { type: String, default: '' }
})

const store = useSignConfigStore()
const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)
const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

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

// 卡片错峰入场（翻页/增删后重放；尊重减少动效偏好）
watch(paged, async () => {
  if (prefersReduced) return
  await nextTick()
  gsap.fromTo(
    '.loc-card',
    { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.35, stagger: 0.05, ease: 'power2.out', clearProps: 'opacity,transform' }
  )
}, { immediate: true })

// 模态框：添加 / 编辑
const showModal = ref(false)
const editingId = ref('')
const saving = ref(false)
const form = reactive({ name: '', address: '', lat: '', lng: '', offset: '' })
// 添加方式：map=高德地图拾取（默认，未配置 Key 时选择器内提示并可一键切手动）/ manual=手动输入
const pickerMode = ref('map')
// 名称回填规则：拾取地址回填到「名称」，仅当用户未手动编辑过名称时回填
// （nameTouched 记录用户是否手改过，避免覆盖用户手填内容）
const nameTouched = ref(false)
// 当前表单坐标映射为拾取器点位（编辑已有位置时自动定位）
const pickedPoint = computed(() =>
  form.lat !== '' && form.lng !== '' && !Number.isNaN(Number(form.lat))
    ? { lat: Number(form.lat), lng: Number(form.lng), address: form.address }
    : null
)
function onPointPicked(p) {
  if (!p || p.lat == null || p.lng == null) return
  form.lat = String(p.lat)
  form.lng = String(p.lng)
  // 拾取地址回填到「名称」：仅当用户尚未手动编辑过名称时回填，避免覆盖手填内容
  // （编辑已有位置时同样生效——重新拾取会把名称更新为拾取到的地址）
  if (p.address && !nameTouched.value) {
    form.name = p.address
  }
}
// 保存校验：名称/地址号/经纬度全部必填
const canSave = computed(() => Boolean(form.name && form.address && form.lat !== '' && form.lng !== ''))

function onNameInput() {
  // 用户手改名称后，自动回填让位（后续拾取不再覆盖手填内容）
  nameTouched.value = true
}

function openAdd() {
  editingId.value = ''
  pickerMode.value = 'map'
  nameTouched.value = false
  form.name = ''
  form.address = ''
  form.lat = ''
  form.lng = ''
  form.offset = 10
  showModal.value = true
}
function openEdit(loc) {
  editingId.value = loc.id
  pickerMode.value = 'map'
  nameTouched.value = false
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

// 删除：两步确认（第一次点出确认条，第二次才真正删除）
const confirmingId = ref(null)
function del(loc) {
  confirmingId.value = loc.id
}
function confirmDel(loc) {
  confirmingId.value = null
  store.deleteLocation({ scope: scope.value, id: loc.id })
}
</script>
