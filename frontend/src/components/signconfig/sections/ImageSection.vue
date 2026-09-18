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
        <div class="space-y-2 pt-1">
          <div>
            <label class="mb-1 block text-xs font-medium text-ink-muted">取图方式</label>
            <BaseSelect v-model="config.image.mode" :options="modeOptions" size="sm" class="w-72" />
            <p class="mt-1 text-xs text-ink-muted">{{ modeHint }}</p>
          </div>

          <div v-if="isByGroup">
            <label class="mb-1 block text-xs font-medium text-ink-muted">按哪类分组</label>
            <BaseSelect v-model="config.image.groupKind" :options="kindOptions" size="sm" class="w-72" />
          </div>

          <div>
            <label class="mb-1 block text-xs font-medium text-ink-muted">
              {{ isByGroup ? '默认图库（分组未绑图库时回退）' : '图片来源分组' }}
            </label>
            <BaseSelect v-model="config.image.groupId" :options="groupOptions" :searchable="true" size="sm" class="w-72" />
            <p class="mt-1 text-xs text-ink-muted">{{ scopeHint }}</p>
          </div>

          <!-- 绑定状态就地可见，省得回分组页逐个核对；管理员无分组，不展示 -->
          <div v-if="isByGroup && !isAdmin" class="rounded-lg bg-cloud/50 px-3 py-2">
            <p class="text-xs" :class="bindTone">{{ bindText }}</p>
            <button
              type="button"
              class="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-brand transition hover:underline"
              @click="router.push('/group-push')"
            >
              <Icon name="send" :size="13" />去分组页绑定图库
            </button>
          </div>

          <div>
            <label class="mb-1 block text-xs font-medium text-ink-muted">图片策略</label>
            <BaseSelect v-model="config.image.strategy" :options="strategyOptions" size="sm" class="w-72" />
          </div>

          <div class="flex items-center gap-2">
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
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ConfigSection from '@/components/signconfig/ConfigSection.vue'
import ConfigToggle from '@/components/signconfig/ConfigToggle.vue'
import GCollapse from '@/components/signconfig/GCollapse.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import Icon from '@/components/Icon.vue'
import { useAuthStore } from '@/stores/auth'
import { useSignConfigStore } from '@/stores/signConfig'
import { fetchGroups } from '@/api/groupPush'

const props = defineProps({
  config: { type: Object, required: true },
  source: { type: String, default: '' }
})

const store = useSignConfigStore()
const auth = useAuthStore()
const router = useRouter()
const isAdmin = computed(() => auth.isAdmin)

const strategyOptions = [
  { label: '循环复用（用毕入回收站续用）', value: 'recycle' },
  { label: '用后删除', value: 'delete' },
  { label: '用后入回收站可恢复', value: 'trash' }
]
const modeOptions = [
  { label: '固定图库', value: 'fixed' },
  { label: '按分组取图', value: 'byGroup' }
]
const kindOptions = [
  { label: '寝室分组', value: 'dorm' },
  { label: '班级分组', value: 'class' }
]
const activeCount = computed(() => store.imageLibrary.filter((i) => !i.inTrash).length)
const trashCount = computed(() => store.imageLibrary.filter((i) => i.inTrash).length)
// 图片来源分组选项：'' = 全部图库（兼容未分组的历史配置），其余为用户自建分组（如寝室号）
const groupOptions = computed(() => [
  { label: '全部图库', value: '' },
  ...store.imageGroups.map((g) => ({ label: g.name, value: g.id }))
])

const isByGroup = computed(() => props.config.image.mode === 'byGroup')
const kindLabel = computed(() => (props.config.image.groupKind === 'class' ? '班级分组' : '寝室分组'))
const modeHint = computed(() => (isByGroup.value
  ? '各账号按所属分组的图库取图，一个配置套就能覆盖多个寝室'
  : '所有账号共用同一个图库，适合单人或单寝室'))
const scopeHint = computed(() => (isByGroup.value
  ? '账号不在任何分组、或分组未绑图库时，回退用这里的默认图库'
  : '只使用所选分组内的照片；同寝室账号选同一分组即共用。分组在「我的资源 → 图库」中管理。'))

// 分组绑定状态：按分组取图下必须能看到「有没有分组真的绑了图库」，
// 否则配置页只会显示一堆悬空回退，用户无从判断问题出在哪。
const groupStats = ref(null)
const bindText = computed(() => {
  const s = groupStats.value
  if (!s) return `${kindLabel.value}的图库归属在「分组」页设置`
  if (!s.total) return `还没有${kindLabel.value}，全部账号都会走默认图库`
  if (!s.bound) return `${s.total} 个${kindLabel.value}都没绑图库，全部账号都会走默认图库`
  if (s.bound === s.total) return `${s.total} 个${kindLabel.value}都已绑定图库`
  return `${s.bound}/${s.total} 个${kindLabel.value}已绑定图库，其余走默认图库`
})
const bindTone = computed(() => (groupStats.value?.bound > 0 ? 'text-ink-muted' : 'text-warning'))

// 快速连点切换分组类型时旧响应可能后到，用序号丢弃过期结果
let statsToken = 0
async function loadGroupStats() {
  if (isAdmin.value) {
    groupStats.value = null
    return
  }
  const kind = props.config.image.groupKind === 'class' ? 'class' : 'dorm'
  const token = ++statsToken
  try {
    const items = await fetchGroups(kind)
    if (token !== statsToken) return
    groupStats.value = { total: items.length, bound: items.filter((g) => g.imageGroupId).length }
  } catch (e) {
    if (token === statsToken) groupStats.value = null
  }
}

onMounted(() => {
  if (isByGroup.value) loadGroupStats()
})

// 必须排在 isByGroup / loadGroupStats 之后：写在前面会在 setup 阶段触发 TDZ
watch([() => props.config.image.mode, () => props.config.image.groupKind], () => {
  groupStats.value = null
  if (isByGroup.value) loadGroupStats()
})
</script>
