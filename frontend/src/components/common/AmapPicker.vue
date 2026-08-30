<template>
  <!-- 未配置高德服务：引导切手动输入 -->
  <div v-if="state === 'nokey'" class="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-ink/15 py-8 text-center">
    <Icon name="map-pin" :size="26" class="opacity-40" />
    <p class="text-sm text-ink-soft">管理员尚未配置高德地图服务</p>
    <p class="text-xs text-ink-muted">可在「系统设置 → 高德地图」中填写 Key 后使用地图拾取</p>
    <button
      type="button"
      class="mt-1 rounded-lg border border-ink/10 px-3 py-1.5 text-xs font-medium text-brand transition hover:bg-brand/5"
      @click="emit('unavailable')"
    >改用手动输入</button>
  </div>

  <div v-else-if="state === 'error'" class="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-danger/30 py-8 text-center">
    <p class="text-sm text-danger">地图加载失败：{{ errMsg }}</p>
    <button type="button" class="rounded-lg border border-ink/10 px-3 py-1.5 text-xs font-medium text-brand transition hover:bg-brand/5" @click="init">重试</button>
  </div>

  <div v-else class="space-y-2.5">
    <!-- 搜索：自建唯一候选列表（无头调用高德输入提示服务），防抖 400ms -->
    <div class="relative">
      <Icon name="search" :size="14" class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted" />
      <input
        v-model="keyword"
        type="text"
        autocomplete="off"
        placeholder="搜索地点，如：学校名称 / 楼栋"
        class="w-full rounded-xl border border-ink/10 bg-white py-2 pl-8 pr-3 text-sm text-ink outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/10"
        @input="onKeywordInput"
        @keydown.enter.prevent="onSearchEnter"
        @focus="onFocusInput"
        @blur="onBlurInput"
      />
      <!-- 候选列表（唯一一个下拉：AMap 以无头模式调用，不再产生自带面板） -->
      <ul
        v-if="tips.length || searching"
        class="absolute inset-x-0 top-full z-10 mt-1 max-h-52 overflow-y-auto rounded-xl border border-ink/10 bg-white py-1 shadow-lg shadow-ink/10"
      >
        <li v-if="searching" class="px-3 py-2 text-xs text-ink-muted">搜索中…</li>
        <li
          v-for="(tip, i) in tips"
          :key="i"
          class="cursor-pointer px-3 py-2 text-sm transition hover:bg-cloud"
          @mousedown.prevent="pickTip(tip)"
        >
          <p class="truncate text-ink">{{ tip.name }}</p>
          <p class="truncate text-xs text-ink-muted">{{ tip.district }} {{ tip.address }}</p>
        </li>
        <li v-if="!searching && tips.length === 0" class="px-3 py-2 text-xs text-ink-muted">未找到匹配地点</li>
      </ul>
    </div>

    <!-- 地图：点击 / 拖拽标记选点 -->
    <div class="relative overflow-hidden rounded-xl border border-ink/10" :style="{ height }">
      <div ref="mapEl" class="h-full w-full"></div>
      <div
        v-if="state === 'loading'"
        class="absolute inset-0 grid place-items-center bg-white/70 text-xs text-ink-muted"
      >地图加载中…</div>
      <span class="pointer-events-none absolute bottom-2 left-2 rounded bg-white/90 px-1.5 py-0.5 text-[10px] text-ink-muted">
        点击地图放置标记，可拖拽微调
      </span>
    </div>

    <!-- 当前坐标 + 地址（逆地理编码自动识别，回填到名称用） -->
    <div class="flex items-center gap-2 rounded-lg bg-cloud/70 px-2.5 py-1.5 text-xs">
      <span class="shrink-0 rounded bg-white px-1.5 py-0.5 tabular-nums text-ink-soft">
        {{ point.lng ?? '—' }}, {{ point.lat ?? '—' }}
      </span>
      <span class="min-w-0 flex-1 truncate text-ink-muted" :title="addr || undefined">
        {{ addr || '点击地图或搜索地点，自动识别地址' }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import request from '@/api/request'
import Icon from '@/components/Icon.vue'

// 高德为 GCJ-02 火星坐标，与 B 平台抓包坐标系一致（首次真机签到建议对比一次精度）
const DEFAULT_CENTER = [106.534989, 29.343984]
const DEBOUNCE_MS = 400
const BLUR_CLOSE_MS = 180

const props = defineProps({
  // { lat, lng, address } 或 null
  modelValue: { type: Object, default: null },
  height: { type: String, default: '320px' },
})
const emit = defineEmits(['update:modelValue', 'unavailable'])

const state = ref('loading') // loading | ready | nokey | error
const errMsg = ref('')
const keyword = ref('')
const tips = ref([]) // 搜索候选（唯一下拉：由本组件渲染，AMap 以无头模式调用不产生自带面板）
const searching = ref(false)
const point = ref({ lat: null, lng: null })
const addr = ref('')

const mapEl = ref(null)
let map = null
let marker = null
let geocoder = null
let autoComplete = null
let AMap = null
let searchTimer = null
let blurTimer = null

function emitPoint(lng, lat, address) {
  point.value = { lat: Number(lat).toFixed(6), lng: Number(lng).toFixed(6) }
  if (address !== undefined && address !== null) addr.value = address
  emit('update:modelValue', {
    lat: Number(Number(lat).toFixed(6)),
    lng: Number(Number(lng).toFixed(6)),
    address: addr.value,
  })
}

function setMarker(lng, lat) {
  const position = [lng, lat]
  if (marker) {
    marker.setPosition(position)
  } else {
    marker = new AMap.Marker({ position, draggable: true })
    marker.on('dragend', () => {
      const p = marker.getPosition()
      if (p) setPoint(p.lng, p.lat)
    })
    map.add(marker)
  }
}

function setPoint(lng, lat, { geocode = true, zoom = false, zoomLevel = 16 } = {}) {
  emitPoint(lng, lat)
  setMarker(lng, lat)
  // 选点可能来自远处（搜索候选），把视野平移+放大到该点，否则标记在屏幕外像"没反应"
  if (zoom && map) map.setZoomAndCenter(zoomLevel, [lng, lat])
  if (geocode && geocoder) {
    geocoder.getAddress([lng, lat], (status, result) => {
      if (status === 'complete' && result.regeocode) {
        addr.value = result.regeocode.formattedAddress || ''
        emit('update:modelValue', {
          lat: Number(Number(lat).toFixed(6)),
          lng: Number(Number(lng).toFixed(6)),
          address: addr.value,
        })
      }
    })
  }
}

async function init() {
  state.value = 'loading'
  try {
    const cfg = await request({ url: '/map/config', method: 'get' })
    if (!cfg.key) {
      state.value = 'nokey'
      return
    }
    // 安全密钥必须在 JS API 脚本加载前注入
    window._AMapSecurityConfig = { securityJsCode: cfg.securityCode }
    AMap = await AMapLoader.load({
      key: cfg.key,
      version: '2.0',
      plugins: ['AMap.Geocoder', 'AMap.AutoComplete', 'AMap.PlaceSearch'],
    })
    await nextTick()
    const initPoint = props.modelValue && props.modelValue.lat ? [props.modelValue.lng, props.modelValue.lat] : DEFAULT_CENTER
    map = new AMap.Map(mapEl.value, { zoom: props.modelValue ? 16 : 14, center: initPoint })
    map.on('click', (e) => setPoint(e.lnglat.lng, e.lnglat.lat))
    geocoder = new AMap.Geocoder()
    if (props.modelValue && props.modelValue.lat) {
      setMarker(initPoint[0], initPoint[1])
      addr.value = props.modelValue.address || ''
    }
    // 无头输入提示：不绑定 input，候选由本组件自建列表渲染（避免高德自带面板与浏览器下拉叠加）
    autoComplete = new AMap.AutoComplete()
    state.value = 'ready'
  } catch (e) {
    state.value = 'error'
    errMsg.value = (e && e.message) || String(e)
  }
}

// ── 搜索（防抖 → 无头输入提示 → 自建候选列表）──
function onKeywordInput() {
  tips.value = []
  clearTimeout(searchTimer)
  const kw = keyword.value.trim()
  if (!kw || state.value !== 'ready' || !autoComplete) return
  searchTimer = setTimeout(() => doSearch(kw), DEBOUNCE_MS)
}

function onSearchEnter() {
  clearTimeout(searchTimer)
  const kw = keyword.value.trim()
  if (!kw || state.value !== 'ready') return
  if (tips.value.length === 1) return pickTip(tips.value[0])
  doSearch(kw)
}

function onFocusInput() {
  clearTimeout(blurTimer)
  // 聚焦时若已有候选（刚搜索过）重新展示，否则按当前关键字补一次搜索
  if (keyword.value.trim() && tips.value.length === 0) onKeywordInput()
}

function onBlurInput() {
  // 延迟关闭：给候选项的 mousedown（prevent 阻止失焦）留出点击窗口
  blurTimer = setTimeout(() => {
    tips.value = []
  }, BLUR_CLOSE_MS)
}

function doSearch(kw) {
  searching.value = true
  autoComplete.search(kw, (status, result) => {
    searching.value = false
    if (status !== 'complete') return
    tips.value = (result?.tips || [])
      .filter((t) => t.location) // 无坐标的区县级候选点击无法定位，过滤
      .map((t) => ({
        name: t.name,
        district: [t.pname, t.cityname, t.adname].filter(Boolean).join(''),
        address: t.address || '',
        location: t.location,
      }))
  })
}

function pickTip(tip) {
  tips.value = []
  setPoint(tip.location.lng, tip.location.lat, { zoom: true })
}

onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  clearTimeout(blurTimer)
  if (map) {
    map.destroy()
    map = null
  }
})

// 外部坐标变化（编辑已有位置打开时）→ 同步标记与展示
watch(() => props.modelValue, (v) => {
  if (v && v.lat && map && marker) {
    const p = marker.getPosition()
    if (!p || Math.abs(p.lng - v.lng) > 1e-6 || Math.abs(p.lat - v.lat) > 1e-6) {
      setMarker(v.lng, v.lat)
      if (v.address) addr.value = v.address
    }
  }
})

onMounted(init)

defineExpose({ init })
</script>
