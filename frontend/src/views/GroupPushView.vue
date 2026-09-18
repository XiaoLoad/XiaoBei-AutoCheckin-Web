<template>
  <div ref="rootRef" class="flex flex-col gap-4 transition-opacity" :class="loading && 'opacity-60'">
    <!-- 页头 -->
    <div class="dash-card fade-up shrink-0 p-4 sm:p-5">
      <div class="flex items-start justify-between gap-4">
        <div>
          <h1 class="text-lg font-semibold text-ink">分组</h1>
          <p class="mt-1 text-sm text-ink-muted">
            把同寝室 / 同班级的账号归到一起。分组有两项用途：绑定图库归属（配置套选「按分组取图」时各组取各自的照片），
            以及把当日的签到结果合并成一条消息推送到对应的 QQ 群——而非每人各发一条。
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

    <!-- 统计卡片：分组数量 + 签到推送概况 -->
    <div class="grid grid-cols-2 gap-3 lg:grid-cols-4 shrink-0">
      <div class="dash-card fade-up p-4">
        <div class="flex items-center gap-2 text-ink-muted">
          <Icon name="box" :size="15" />
          <span class="text-xs font-medium">分组总数</span>
        </div>
        <p class="mt-2 text-2xl font-semibold tabular-nums text-ink">{{ stat.totalGroups }}</p>
        <p class="mt-1 text-xs text-ink-muted">班级 {{ stat.classCount }} · 寝室 {{ stat.dormCount }}</p>
      </div>

      <div class="dash-card fade-up p-4">
        <div class="flex items-center gap-2 text-ink-muted">
          <Icon name="check-circle" :size="15" />
          <span class="text-xs font-medium">今日已签</span>
        </div>
        <p class="mt-2 text-2xl font-semibold tabular-nums text-ink">{{ stat.total ? stat.done + '/' + stat.total : '—' }}</p>
        <p class="mt-1 text-xs text-ink-muted">{{ stat.total ? stat.pct + '% 完成' : '暂无数据' }}</p>
      </div>

      <div class="dash-card fade-up p-4">
        <div class="flex items-center gap-2 text-ink-muted">
          <Icon name="send" :size="15" />
          <span class="text-xs font-medium">今日已推送</span>
        </div>
        <p class="mt-2 text-2xl font-semibold tabular-nums text-ink">{{ stat.pushed }}</p>
        <p class="mt-1 text-xs text-ink-muted">共 {{ stat.totalGroups }} 个分组</p>
      </div>

      <div class="dash-card fade-up p-4">
        <div class="flex items-center gap-2 text-ink-muted">
          <Icon name="alert" :size="15" />
          <span class="text-xs font-medium">发送失败</span>
        </div>
        <p class="mt-2 text-2xl font-semibold tabular-nums" :class="stat.fail ? 'text-danger' : 'text-ink'">{{ stat.fail }}</p>
        <p class="mt-1 text-xs text-ink-muted">{{ stat.fail ? stat.fail + ' 个发送失败' : '今日无失败' }}</p>
      </div>
    </div>

    <!-- 主从两栏：左分组列表 / 右分组详情（本页无底部分页，整体随内容增高、整页滚动，不锁视口高度） -->
    <div class="flex flex-col gap-4 lg:flex-row lg:items-start">
      <!-- 左：分组列表 -->
      <div ref="leftCardRef" class="dash-card fade-up flex flex-col overflow-hidden rounded-2xl lg:w-80 lg:shrink-0">
        <div class="flex items-center justify-between px-4 pt-4">
          <span class="text-sm font-medium text-ink-soft">分组</span>
          <span class="text-xs text-ink-muted">{{ filteredGroups.length }} 个</span>
        </div>

        <!-- 模糊搜索：姓名 / 学号 / 小北账号 / 分组名，命中即定位到所属分组 -->
        <div class="px-4 pt-3">
          <div class="relative">
            <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索姓名 / 学号 / 小北账号"
              class="login-input w-full py-2 pl-9 pr-9 text-sm"
            />
            <button
              v-if="searchQuery"
              type="button"
              class="absolute right-2 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-full text-ink-muted transition hover:bg-cloud hover:text-ink"
              aria-label="清除搜索"
              @click="searchQuery = ''"
            >✕</button>
          </div>
        </div>

        <div v-if="activeGroups.length === 0" class="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-10 text-center text-sm text-ink-muted">
          <Icon :name="activeTab === 'class' ? 'members' : 'box'" :size="26" class="opacity-50" />
          <span>{{ activeTab === 'class' ? '暂无班级信息：账号校验通过后会自动带回班级字段。' : '还没有寝室分组，点击下方「新建分组」把同寝室账号归到一起，顺带绑定这个寝室的图库。' }}</span>
        </div>

        <div v-else-if="filteredGroups.length === 0" class="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-10 text-center text-sm text-ink-muted">
          <Icon name="search" :size="26" class="opacity-50" />
          <span>没有分组包含与「{{ searchQuery }}」相关的成员</span>
        </div>

        <div v-else class="p-3">
          <button
            v-for="item in filteredGroups"
            :key="item.group.id ?? item.group.name"
            type="button"
            class="mb-2 w-full rounded-xl border px-3 py-2.5 text-left transition"
            :class="isSelected(item.group) ? 'border-brand/30 bg-brand/10' : 'border-transparent hover:bg-cloud/50'"
            @click="selectGroup(item.group)"
          >
            <div class="flex items-center gap-3">
              <span class="h-2.5 w-2.5 shrink-0 rounded-full" :class="statusDot(item.group.today)" />
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-medium text-ink">{{ item.group.name }}</p>
                <p class="mt-0.5 truncate text-xs text-ink-muted">{{ item.group.memberCount }} 名成员</p>
              </div>
              <span class="shrink-0 text-xs" :class="statusTextClass(item.group.today)">{{ statusShort(item.group.today) }}</span>
            </div>
            <p v-if="searchQuery && item.hits.length" class="mt-1.5 truncate text-xs text-brand">
              命中：{{ item.hits.map((h) => h.name || h.account).join('、') }}
            </p>
          </button>
        </div>

        <!-- 寝室：新建入口 -->
        <div v-if="activeTab === 'dorm'" class="border-t border-ink/5 p-3">
          <button
            type="button"
            class="flex w-full items-center justify-center gap-1.5 rounded-xl bg-brand px-3.5 py-2 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark"
            @click="openCreate"
          >
            <Icon name="plus" :size="17" />新建分组
          </button>
        </div>
      </div>

      <!-- 右：分组详情 -->
      <div ref="rightCardRef" class="dash-card fade-up flex flex-col overflow-hidden rounded-2xl lg:flex-1">
        <div v-if="!selectedGroup" class="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-10 text-center text-sm text-ink-muted">
          <Icon name="send" :size="28" class="opacity-50" />
          <span>从左侧选择一个分组，查看成员与今日推送详情。</span>
        </div>

        <template v-else>
          <div class="p-4 sm:p-5">
            <!-- 头部 -->
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div class="flex items-center gap-2">
                  <h2 class="text-base font-semibold text-ink">{{ selectedGroup.name }}</h2>
                  <span class="rounded-md bg-cloud px-2 py-0.5 text-xs text-ink-muted">{{ selectedGroup.type === 'class' ? '班级' : '寝室' }}</span>
                </div>
                <div class="mt-2"><StatusBadge :today="selectedGroup.today" /></div>
              </div>
              <div class="flex items-center gap-2">
                <button
                  v-if="selectedGroup.bound"
                  type="button"
                  :disabled="flushing"
                  class="inline-flex items-center gap-1.5 rounded-xl bg-brand px-3.5 py-2 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:opacity-60"
                  @click="flush(selectedGroup)"
                >
                  <Icon name="send" :size="15" />{{ flushing ? '发送中' : '立即发送' }}
                </button>
                <button
                  v-else
                  type="button"
                  class="rounded-xl border border-ink/10 px-3.5 py-2 text-sm font-medium text-ink-muted"
                  disabled
                >未绑定 QQ 群</button>
                <button
                  v-if="selectedGroup.type === 'dorm'"
                  type="button"
                  class="rounded-xl border border-ink/10 px-3.5 py-2 text-sm font-medium text-danger transition hover:bg-danger/10"
                  @click="askDelete(selectedGroup)"
                >删除</button>
              </div>
            </div>

            <!-- 签名：今日推送节奏 -->
            <div class="mt-4 rounded-xl bg-cloud/40 p-4">
              <p class="mb-3 text-xs font-medium text-ink-muted">今日推送节奏</p>
              <div class="flex items-center">
                <div class="flex-1 text-center">
                  <div class="mx-auto grid h-7 w-7 place-items-center rounded-full bg-brand/10 text-xs font-semibold text-brand">1</div>
                  <p class="mt-1.5 text-xs text-ink-muted">{{ selectedGroup.memberCount }} 名成员</p>
                </div>
                <div class="h-px flex-1 bg-ink/10"></div>
                <div class="flex-1 text-center">
                  <div class="mx-auto grid h-7 w-7 place-items-center rounded-full text-xs font-semibold" :class="step2Class">{{ step2Label.main }}</div>
                  <p class="mt-1.5 text-xs text-ink-muted">{{ step2Label.sub }}</p>
                </div>
                <div class="h-px flex-1 bg-ink/10"></div>
                <div class="flex-1 text-center">
                  <div class="mx-auto grid h-7 w-7 place-items-center rounded-full text-xs font-semibold" :class="step3Class">{{ step3Glyph }}</div>
                  <p class="mt-1.5 text-xs text-ink-muted">{{ step3Label }}</p>
                </div>
              </div>
            </div>

            <!-- QQ 群绑定 -->
            <div class="mt-4">
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-sm font-medium text-ink-soft">QQ 群编码（qq_code）</p>
                  <p v-if="!editingQQ" class="mt-1 text-sm text-ink">{{ selectedGroup.qqCode || '未绑定，填后推送' }}</p>
                </div>
                <button
                  v-if="!editingQQ"
                  type="button"
                  class="rounded-lg border border-ink/10 px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:bg-cloud"
                  @click="startEditQQ"
                >编辑</button>
              </div>
              <div v-if="editingQQ" class="mt-2 flex items-center gap-2">
                <input v-model="qqDraft" type="text" placeholder="如 dorm829" class="login-input w-full py-1.5 text-sm" />
                <button
                  type="button"
                  class="shrink-0 rounded-lg bg-brand px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-brand-dark disabled:opacity-60"
                  :disabled="savingQQ"
                  @click="saveQQ"
                >{{ savingQQ ? '保存中' : '保存' }}</button>
                <button
                  type="button"
                  class="shrink-0 rounded-lg border border-ink/10 px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:bg-cloud"
                  @click="cancelEditQQ"
                >取消</button>
              </div>
            </div>

            <!-- 图库归属：配置套图片策略选「按分组取图」时，本组账号按此取图 -->
            <div class="mt-4">
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-sm font-medium text-ink-soft">图库归属</p>
                  <p v-if="!editingImage" class="mt-1 text-sm" :class="selectedGroup.imageGroupId ? 'text-ink' : 'text-ink-muted'">
                    {{ selectedGroup.imageGroupId ? imageGroupLabel(selectedGroup.imageGroupId) : '未绑定，走配置套默认图库' }}
                  </p>
                </div>
                <button
                  v-if="!editingImage"
                  type="button"
                  class="rounded-lg border border-ink/10 px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:bg-cloud"
                  @click="startEditImage"
                >编辑</button>
              </div>
              <div v-if="editingImage" class="mt-2 flex items-center gap-2">
                <BaseSelect v-model="imageDraft" :options="imageGroupOptions" :searchable="true" size="sm" class="w-full" />
                <button
                  type="button"
                  class="shrink-0 rounded-lg bg-brand px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-brand-dark disabled:opacity-60"
                  :disabled="savingImage"
                  @click="saveImageGroup"
                >{{ savingImage ? '保存中' : '保存' }}</button>
                <button
                  type="button"
                  class="shrink-0 rounded-lg border border-ink/10 px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:bg-cloud"
                  @click="cancelEditImage"
                >取消</button>
              </div>
              <p v-if="editingImage" class="mt-1.5 text-xs text-ink-muted">
                未绑定图库的分组，其成员按配置套的默认图库取图。图库分组在「签到配置 → 我的资源 → 图库」中维护。
              </p>
            </div>

            <!-- 成员 -->
            <div class="mt-4 border-t border-ink/5 pt-4">
              <div class="flex items-center justify-between">
                <p class="text-sm font-medium text-ink-soft">成员（{{ memberList.length }}）</p>
                <button
                  v-if="selectedGroup.type === 'dorm'"
                  type="button"
                  class="rounded-lg bg-brand/10 px-3 py-1.5 text-xs font-medium text-brand transition hover:bg-brand/15"
                  @click="openAdd"
                >添加成员</button>
              </div>
              <p v-if="selectedGroup.type === 'class'" class="mt-2 text-xs text-ink-muted">由账号「班级」字段自动归类，成员随账号信息实时更新，无需手动维护。</p>

              <div v-if="memberList.length === 0" class="mt-2 rounded-xl border border-dashed border-ink/10 px-3 py-6 text-center text-sm text-ink-muted">暂无成员</div>
              <div v-else class="mt-3">
                <!-- 寝室：可移除胶囊 -->
                <div v-if="selectedGroup.type === 'dorm'" class="flex flex-wrap gap-2">
                  <span
                    v-for="m in memberList"
                    :key="m.accountId"
                    class="inline-flex items-center gap-2 rounded-full bg-cloud/50 py-1 pl-1 pr-2 text-sm"
                  >
                    <span class="grid h-6 w-6 place-items-center rounded-full bg-brand/10 text-xs font-medium text-brand">{{ initial(m.name || m.account) }}</span>
                    <span class="max-w-[8rem] truncate text-ink">{{ m.name || m.account }}</span>
                    <button
                      type="button"
                      class="shrink-0 text-danger/70 transition hover:text-danger"
                      aria-label="移除成员"
                      @click="askRemoveMember(m)"
                    >✕</button>
                  </span>
                </div>
                <!-- 班级：只读列表 -->
                <div v-else>
                  <div
                    v-for="m in memberList"
                    :key="m.accountId"
                    class="flex items-center gap-3 border-b border-ink/10 py-2 last:border-0"
                  >
                    <span class="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand/10 text-xs font-medium text-brand">{{ initial(m.name || m.account) }}</span>
                    <div class="min-w-0">
                      <p class="truncate text-sm text-ink">{{ m.name || m.account }}</p>
                      <p class="truncate text-xs text-ink-muted">{{ m.account }} · {{ m.className || '—' }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 新建分组弹窗 -->
    <BaseModal v-model="createOpen" title="新建寝室分组" size="md">
      <div class="space-y-4">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">分组名称</label>
          <input v-model="createForm.name" type="text" placeholder="如：3栋507" class="login-input w-full py-2 text-sm" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">QQ 群编码（qq_code）<span class="text-ink-muted">（可选）</span></label>
          <input v-model="createForm.qqCode" type="text" placeholder="留空可稍后绑定" class="login-input w-full py-2 text-sm" />
          <p class="mt-1.5 text-xs text-ink-muted">未绑定 QQ 群前不会推送；可在右侧详情随时编辑。</p>
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">图库归属<span class="text-ink-muted">（可选）</span></label>
          <BaseSelect v-model="createForm.imageGroupId" :options="imageGroupOptions" :searchable="true" size="sm" class="w-full" />
          <p class="mt-1.5 text-xs text-ink-muted">配置套图片策略选「按分组取图」时，本组账号按此图库取图；不绑定则走配置套默认图库。</p>
        </div>
      </div>
      <template #footer>
        <button type="button" class="flex-1 rounded-xl border border-ink/10 py-2.5 text-sm font-medium text-ink-soft transition hover:bg-cloud" @click="createOpen = false">取消</button>
        <button
          type="button"
          class="flex-1 rounded-xl bg-brand py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:opacity-60"
          :disabled="!createForm.name.trim() || creating"
          @click="submitCreate"
        >{{ creating ? '创建中' : '创建' }}</button>
      </template>
    </BaseModal>

    <!-- 添加成员弹窗（单一目的，干净不堆叠） -->
    <BaseModal v-model="addOpen" :title="`添加成员 · ${selectedGroup ? selectedGroup.name : ''}`" size="2xl">
      <div v-if="filteredAddAccounts.length === 0 && !addKeyword" class="py-6 text-center text-sm text-ink-muted">该分组已包含所有可用账号</div>
      <template v-else>
        <div class="relative mb-3 w-full sm:w-72">
          <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input v-model="addKeyword" type="text" placeholder="搜索账号 / 姓名" class="login-input py-2 pl-9 text-sm" />
        </div>
        <div class="xb-scroll max-h-60 overflow-auto rounded-xl border border-ink/5">
          <label
            v-for="a in filteredAddAccounts"
            :key="a.id"
            class="flex cursor-pointer items-center gap-3 border-b border-ink/5 px-3 py-2.5 transition hover:bg-cloud/50"
          >
            <BaseCheckbox :model-value="selectedAccountIds.includes(a.id)" @update:model-value="toggleSelect(a.id, $event)" />
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm text-ink">{{ (a.profile && a.profile.name) || '未命名' }}</p>
              <p class="truncate text-xs text-ink-muted">{{ a.account }} · {{ (a.profile && a.profile.className) || '—' }}</p>
            </div>
          </label>
          <div v-if="filteredAddAccounts.length === 0" class="px-3 py-6 text-center text-sm text-ink-muted">无匹配账号</div>
        </div>
      </template>
      <template #footer>
        <button type="button" class="flex-1 rounded-xl border border-ink/10 py-2.5 text-sm font-medium text-ink-soft transition hover:bg-cloud" @click="addOpen = false">关闭</button>
        <button
          type="button"
          class="flex-1 rounded-xl bg-brand py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:opacity-60"
          :disabled="selectedAccountIds.length === 0 || addingMembers"
          @click="submitAddMembers"
        >{{ addingMembers ? '添加中' : `添加 ${selectedAccountIds.length} 人` }}</button>
      </template>
    </BaseModal>

    <!-- 删除确认 -->
    <ConfirmModal
      v-model="deleteOpen"
      title="删除寝室分组"
      :message="deleteTarget ? `确定删除寝室分组「${deleteTarget.name}」？成员关系与图库归属将一并清除（图片本身留在图库中），且不可恢复。` : ''"
      danger
      confirming-text="删除中…"
      @confirm="confirmDelete"
    />

    <!-- 移除成员确认 -->
    <ConfirmModal
      v-model="removeOpen"
      title="移除成员"
      :message="removingMember ? `确定将成员「${removingMember.name || removingMember.account}」从分组「${selectedGroup ? selectedGroup.name : ''}」移除？移除后该成员不再参与本群组的合并推送。` : ''"
      danger
      confirming-text="移除中…"
      @confirm="confirmRemoveMember"
      @cancel="removingMember = null"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import Icon from '@/components/Icon.vue'
import BaseModal from '@/components/BaseModal.vue'
import BaseCheckbox from '@/components/BaseCheckbox.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { toast } from '@/utils/toast'
import { gsap } from 'gsap'
import {
  fetchGroups, createDormGroup, updateDormGroup, deleteDormGroup,
  fetchMembers, addMembers, removeMember, bindClassGroup, flushGroup
} from '@/api/groupPush'
import { fetchAccounts } from '@/api/accounts'
import { fetchImageGroups } from '@/api/signConfig'

const tabs = [
  { key: 'class', label: '班级分组' },
  { key: 'dorm', label: '寝室分组' }
]
const activeTab = ref('class')

const loading = ref(false)
const classGroups = ref([])
const dormGroups = ref([])
const allAccounts = ref([])
const selected = ref(null) // { type, key }，key = id ?? name
const flushing = ref(false)

// 新建分组弹窗
const createOpen = ref(false)
const creating = ref(false)
const createForm = ref({ name: '', qqCode: '', imageGroupId: '' })

// QQ 绑定内联编辑
const editingQQ = ref(false)
const qqDraft = ref('')
const savingQQ = ref(false)

// 图库归属内联编辑
const imageGroups = ref([])
const editingImage = ref(false)
const imageDraft = ref('')
const savingImage = ref(false)

// 图库归属下拉：'' = 不绑定（回退配置套默认图库），其余为「我的资源 → 图库」里建的分组
const imageGroupOptions = computed(() => [
  { label: '不绑定（走配置套默认图库）', value: '' },
  ...imageGroups.value.map((g) => ({ label: g.name, value: g.id }))
])

// 已绑图库的展示名：图库分组被删时后端已自动解绑（ON DELETE SET NULL），此处仅作文案兜底
function imageGroupLabel(id) {
  const g = imageGroups.value.find((x) => String(x.id) === String(id))
  return g ? g.name : '原图库分组已删除'
}

// 成员
const addOpen = ref(false)

// 模糊搜索 + 全量成员索引（用于「搜学生 → 定位所属分组」）
const searchQuery = ref('')
const dormMembersMap = ref({}) // groupId -> [{accountId, account, name, className, studentNo}]
const addingMembers = ref(false)
const addKeyword = ref('')
const selectedAccountIds = ref([])

// 删除确认
const deleteOpen = ref(false)
const deleting = ref(false)
const deleteTarget = ref(null)

// 移除成员二次确认
const removeOpen = ref(false)
const removingMember = ref(null)

const activeGroups = computed(() => (activeTab.value === 'class' ? classGroups.value : dormGroups.value))

const selectedGroup = computed(() => {
  if (!selected.value) return null
  return activeGroups.value.find(
    (g) => g.type === selected.value.type && (g.id ?? g.name) === selected.value.key
  ) || null
})

// 班级成员：按 className 实时派生（只读）；寝室：接口拉取
const memberList = computed(() => {
  if (!selectedGroup.value) return []
  const g = selectedGroup.value
  if (g.type === 'dorm') return dormMembersMap.value[g.id] || []
  const name = g.name
  return allAccounts.value
    .filter((a) => (a.profile && a.profile.className) === name)
    .map((a) => ({
      accountId: a.id,
      account: a.account,
      name: (a.profile && a.profile.name) || '',
      className: (a.profile && a.profile.className) || '',
      studentNo: (a.profile && a.profile.studentNo) || ''
    }))
})

const filteredAddAccounts = computed(() => {
  const kw = addKeyword.value.trim().toLowerCase()
  const ids = new Set(memberList.value.map((m) => m.accountId))
  return allAccounts.value
    .filter((a) => !ids.has(a.id))
    .filter((a) => {
      if (!kw) return true
      const name = (a.profile && a.profile.name) || ''
      return a.account.toLowerCase().includes(kw) || name.toLowerCase().includes(kw)
    })
})

// 归一化用于模糊匹配
const norm = (s) => (s == null ? '' : String(s)).toLowerCase().trim()

// 取某分组的全量成员（班级按 className 派生；寝室读预载的成员索引）
function membersOf(g) {
  if (g.type === 'dorm') return dormMembersMap.value[g.id] || []
  return allAccounts.value
    .filter((a) => (a.profile && a.profile.className) === g.name)
    .map((a) => ({
      accountId: a.id,
      account: a.account,
      name: (a.profile && a.profile.name) || '',
      className: (a.profile && a.profile.className) || '',
      studentNo: (a.profile && a.profile.studentNo) || ''
    }))
}

// 左侧分组列表：按学生姓名 / 小北账号 / 学号 / 分组名模糊过滤，并回传命中成员
const filteredGroups = computed(() => {
  const q = norm(searchQuery.value)
  const list = activeGroups.value
  if (!q) return list.map((g) => ({ group: g, hits: [] }))
  const out = []
  for (const g of list) {
    const hits = membersOf(g).filter(
      (m) =>
        norm(m.name).includes(q) ||
        norm(m.account).includes(q) ||
        norm(m.studentNo).includes(q)
    )
    if (hits.length > 0 || norm(g.name).includes(q)) {
      out.push({ group: g, hits: hits.length ? hits : [] })
    }
  }
  return out
})

// 顶部统计卡片数据（分组数量 + 签到推送概况）
const stat = computed(() => {
  const all = [...classGroups.value, ...dormGroups.value]
  let done = 0
  let total = 0
  let pushed = 0
  let fail = 0
  for (const g of all) {
    const t = g.today
    if (!t) continue
    done += t.memberDone || 0
    total += t.memberTotal || 0
    if (t.status === 'success' || t.status === 'partial') pushed += 1
    if (t.status === 'fail') fail += 1
  }
  return {
    totalGroups: all.length,
    classCount: classGroups.value.length,
    dormCount: dormGroups.value.length,
    done,
    total,
    pushed,
    fail,
    pct: total > 0 ? Math.round((done / total) * 100) : 0
  }
})

// 预载所有寝室分组的成员（含学号，便于跨组检索）；账号增删后刷新
async function loadDormMembersMap() {
  const groups = dormGroups.value
  try {
    const entries = await Promise.all(
      groups.map(async (g) => {
        const rows = await fetchMembers(g.id)
        const enriched = rows.map((r) => {
          const acc = allAccounts.value.find((a) => a.id === r.accountId)
          return {
            accountId: r.accountId,
            account: r.account,
            name: r.name,
            className: r.className,
            studentNo: (acc && acc.profile && acc.profile.studentNo) || ''
          }
        })
        return [g.id, enriched]
      })
    )
    dormMembersMap.value = Object.fromEntries(entries)
  } catch (e) {
    /* toast by interceptor */
  }
}

// ── 今日推送节奏步骤条 ──
const step2Label = computed(() => {
  const t = selectedGroup.value && selectedGroup.value.today
  if (t && t.memberTotal > 0) return { main: `${t.memberDone}/${t.memberTotal}`, sub: '已签' }
  return { main: '—', sub: '待签到' }
})
const step2Class = computed(() => {
  const t = selectedGroup.value && selectedGroup.value.today
  if (t && t.memberTotal > 0 && t.memberDone === t.memberTotal) return 'bg-success/10 text-success'
  if (t) return 'bg-warning/10 text-warning'
  return 'bg-ink/10 text-ink-muted'
})
const step3Label = computed(() => {
  const t = selectedGroup.value && selectedGroup.value.today
  if (t && (t.status === 'success' || t.status === 'partial')) return `已推送 ${t.sentAt ? t.sentAt.slice(11) : ''}`
  if (t && t.status === 'fail') return '发送失败'
  return '待推送'
})
const step3Class = computed(() => {
  const t = selectedGroup.value && selectedGroup.value.today
  if (t && t.status === 'success') return 'bg-success/10 text-success'
  if (t && t.status === 'partial') return 'bg-warning/10 text-warning'
  if (t && t.status === 'fail') return 'bg-danger/10 text-danger'
  return 'bg-ink/10 text-ink-muted'
})
const step3Glyph = computed(() => {
  const t = selectedGroup.value && selectedGroup.value.today
  if (t && (t.status === 'success' || t.status === 'partial')) return '✓'
  if (t && t.status === 'fail') return '!'
  return '·'
})

// ── 列表状态 helpers ──
function statusDot(today) {
  if (!today) return 'bg-ink/30'
  if (today.status === 'success') return 'bg-success'
  if (today.status === 'partial') return 'bg-warning'
  return 'bg-danger'
}
function statusTextClass(today) {
  if (!today) return 'text-ink-muted'
  if (today.status === 'success') return 'text-success'
  if (today.status === 'partial') return 'text-warning'
  return 'text-danger'
}
function statusShort(today) {
  if (!today) return '待推送'
  if (today.status === 'success') return '已推送'
  if (today.status === 'partial') return '部分'
  return '发送失败'
}
function initial(name) {
  return (name || '?').trim().charAt(0).toUpperCase()
}

function isSelected(g) {
  return !!selected.value && selected.value.type === g.type && selected.value.key === (g.id ?? g.name)
}

async function loadGroups() {
  loading.value = true
  try {
    const [cls, dorm] = await Promise.all([fetchGroups('class'), fetchGroups('dorm')])
    classGroups.value = cls.map((g) => ({ ...g, _qq: g.qqCode }))
    dormGroups.value = dorm.map((g) => ({ ...g, _qq: g.qqCode }))
    ensureSelection()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    loading.value = false
  }
}

async function loadAccounts() {
  try {
    allAccounts.value = await fetchAccounts()
  } catch (e) {
    /* toast by interceptor */
  }
}

async function loadImageGroups() {
  try {
    imageGroups.value = await fetchImageGroups()
  } catch (e) {
    /* toast by interceptor */
  }
}

function ensureSelection() {
  const list = activeGroups.value
  if (list.length === 0) {
    selected.value = null
    return
  }
  // 命中判据带上 name：班级分组行首次落库后 id ?? name 由「名字」变「id」，
  // 只比 key 会让刚绑完 QQ / 图库的这次刷新把选中项弹走
  if (selected.value && list.some((g) => g.type === selected.value.type &&
    ((g.id ?? g.name) === selected.value.key || g.name === selected.value.key))) {
    return
  }
  selectGroup(list[0])
}

function selectGroup(g) {
  selected.value = { type: g.type, key: g.id ?? g.name }
  editingQQ.value = false
  editingImage.value = false
}

function startEditQQ() {
  qqDraft.value = selectedGroup.value.qqCode || ''
  editingQQ.value = true
}
function cancelEditQQ() {
  editingQQ.value = false
  qqDraft.value = ''
}

function startEditImage() {
  if (!selectedGroup.value) return
  const cur = selectedGroup.value.imageGroupId
  imageDraft.value = cur == null ? '' : String(cur)
  editingImage.value = true
}
function cancelEditImage() {
  editingImage.value = false
  imageDraft.value = ''
}
async function saveImageGroup() {
  if (!selectedGroup.value) return
  savingImage.value = true
  try {
    const imageGroupId = imageDraft.value === '' ? null : imageDraft.value
    if (selectedGroup.value.type === 'dorm') {
      await updateDormGroup(selectedGroup.value.id, { imageGroupId })
    } else {
      // 班级分组可能尚未落库（没绑 QQ 时没有行），接口按 (type=class, name) upsert
      await bindClassGroup({ name: selectedGroup.value.name, imageGroupId })
    }
    toast('图库归属已保存', 'success')
    editingImage.value = false
    await loadGroups()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    savingImage.value = false
  }
}
async function saveQQ() {
  if (!selectedGroup.value) return
  savingQQ.value = true
  try {
    const code = qqDraft.value.trim()
    if (selectedGroup.value.type === 'dorm') {
      await updateDormGroup(selectedGroup.value.id, { qqCode: code })
    } else {
      await bindClassGroup({ name: selectedGroup.value.name, qqCode: code })
    }
    toast('已保存', 'success')
    editingQQ.value = false
    await loadGroups()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    savingQQ.value = false
  }
}

async function flush(g) {
  flushing.value = g.id
  try {
    const res = await flushGroup({ type: g.type, id: g.id, name: g.name })
    const t = res && res.today
    toast(t ? `已发送（${statusShort(t)}）` : '已触发发送', 'success')
    await loadGroups()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    flushing.value = null
  }
}

function openCreate() {
  createForm.value = { name: '', qqCode: '', imageGroupId: '' }
  createOpen.value = true
}
async function submitCreate() {
  creating.value = true
  try {
    await createDormGroup({
      name: createForm.value.name.trim(),
      qqCode: createForm.value.qqCode.trim(),
      imageGroupId: createForm.value.imageGroupId || null
    })
    toast('分组已创建', 'success')
    createOpen.value = false
    await loadGroups()
    await loadDormMembersMap()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    creating.value = false
  }
}

function askDelete(g) {
  deleteTarget.value = g
  deleteOpen.value = true
}
async function confirmDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await deleteDormGroup(deleteTarget.value.id)
    toast('已删除', 'success')
    if (isSelected(deleteTarget.value)) selected.value = null
    deleteOpen.value = false
    await loadGroups()
    await loadDormMembersMap()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    deleting.value = false
  }
}

function openAdd() {
  addKeyword.value = ''
  selectedAccountIds.value = []
  addOpen.value = true
}
function toggleSelect(id, checked) {
  if (checked) {
    if (!selectedAccountIds.value.includes(id)) selectedAccountIds.value = [...selectedAccountIds.value, id]
  } else {
    selectedAccountIds.value = selectedAccountIds.value.filter((x) => x !== id)
  }
}
async function submitAddMembers() {
  if (!selectedGroup.value) return
  addingMembers.value = true
  try {
    const ids = selectedAccountIds.value
    const res = await addMembers(selectedGroup.value.id, ids)
    toast(`已添加 ${res && res.added != null ? res.added : ids.length} 人`, 'success')
    selectedAccountIds.value = []
    addOpen.value = false
    await loadDormMembersMap()
    await loadGroups()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    addingMembers.value = false
  }
}
async function removeMemberFromGroup(id) {
  if (!selectedGroup.value) return
  try {
    await removeMember(selectedGroup.value.id, id)
    await loadDormMembersMap()
    await loadGroups()
  } catch (e) {
    /* toast by interceptor */
  }
}

// 寝室成员移除：先弹二次确认，确认后再真正调用接口（避免误触把人移出分组）
function askRemoveMember(m) {
  removingMember.value = m
  removeOpen.value = true
}
async function confirmRemoveMember() {
  if (!removingMember.value) return
  await removeMemberFromGroup(removingMember.value.accountId)
  removeOpen.value = false
  removingMember.value = null
}

watch(() => activeTab.value, () => {
  if (norm(searchQuery.value)) {
    const m = filteredGroups.value
    if (m.length) selectGroup(m[0].group)
    else selected.value = null
  } else {
    ensureSelection()
  }
})

// 仅一个命中分组时直接选中（搜学生 → 定位分组一步到位）
watch(searchQuery, (q) => {
  const nq = norm(q)
  if (!nq) {
    ensureSelection()
    return
  }
  const m = filteredGroups.value
  if (m.length === 1) selectGroup(m[0].group)
})

// GSAP 高度过渡：切分组 / 成员增减 / 切 tab / 搜索过滤都会改变卡片高度，
// 这里把「高度跳变」补成平滑过渡。复用项目的高度补间范式：
// 在 DOM 重排前（watch 默认 flush:'pre'）量出旧盒高 → nextTick 后量出新盒高 →
// fromTo 锁到旧高再补到新高，onComplete clearProps 交还类上的自适应高度。
// 尊重 prefers-reduced-motion；作用域限定到根节点、卸载时 revert 回收。
// 注意：本块引用的 selectedGroup / memberList / filteredGroups 均在上方先定义，
// 必须排在它们之后，否则 setup 阶段 watch 取初值会触发 TDZ（ComputedRef 未初始化即访问）。
const rootRef = ref(null)
const leftCardRef = ref(null)
const rightCardRef = ref(null)
let animCtx = null
const reduceMotion =
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

function animateHeight(el) {
  if (!el || !animCtx || reduceMotion) return
  const prev = el.getBoundingClientRect().height
  nextTick().then(() => {
    if (!el.isConnected) return
    const next = el.getBoundingClientRect().height
    if (Math.abs(prev - next) < 0.5) return
    animCtx.add(() => {
      gsap.fromTo(
        el,
        { height: prev },
        {
          height: next,
          duration: 0.34,
          ease: 'power2.out',
          overwrite: true,
          onComplete: () => gsap.set(el, { clearProps: 'height' })
        }
      )
    })
  })
}

// 高度变化的「结构签名」：命中才触发补间，避免无关响应式更新反复量高
const rightAnimKey = computed(() => {
  const g = selectedGroup.value
  const id = g ? g.id ?? g.name : 'none'
  const bind = g ? `${g.qqCode || ''}|${g.imageGroupId || ''}` : ''
  return `${id}|${memberList.value.length}|${editingQQ.value ? 1 : 0}|${editingImage.value ? 1 : 0}|${bind}`
})
const leftAnimKey = computed(() => `${activeTab.value}|${filteredGroups.value.length}`)

watch(rightAnimKey, () => animateHeight(rightCardRef.value))
watch(leftAnimKey, () => animateHeight(leftCardRef.value))

onMounted(async () => {
  // GSAP 上下文：作用域限定到组件根，卸载时统一 revert 回收所有补间，避免内存泄漏
  if (rootRef.value) {
    animCtx = gsap.context(() => {}, rootRef.value)
  }
  await Promise.all([loadGroups(), loadAccounts(), loadImageGroups()])
  await loadDormMembersMap()
})

onUnmounted(() => {
  animCtx?.revert()
})
</script>
