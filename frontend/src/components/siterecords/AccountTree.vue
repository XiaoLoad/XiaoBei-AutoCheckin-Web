<template>
  <div class="flex min-h-0 flex-col overflow-hidden rounded-2xl">
    <!-- 头部：标题 + 计数 + 模糊搜索 -->
    <div class="shrink-0 border-b border-ink/5 px-4 pb-3 pt-4">
      <div class="flex items-baseline gap-2">
        <h3 class="text-sm font-semibold text-ink">账号树</h3>
        <span class="text-xs text-ink-muted tabular-nums">{{ treeCounts.users }} 位用户 · {{ treeCounts.accounts }} 个账号</span>
      </div>
      <div class="mt-2.5 flex items-center gap-2 rounded-xl bg-cloud px-3 py-2">
        <Icon name="search" :size="15" class="shrink-0 text-ink-muted" />
        <input
          :value="keyword"
          type="text"
          placeholder="搜索用户名 / B 平台账号…"
          class="min-w-0 flex-1 bg-transparent text-[13px] text-ink outline-none placeholder:text-ink-muted/60"
          @input="keyword = $event.target.value"
        />
        <span class="shrink-0 rounded-md border border-ink/10 bg-white px-1.5 py-0.5 text-[10.5px] text-ink-muted">模糊</span>
      </div>
      <p class="mt-2 px-0.5 text-[11px] leading-relaxed text-ink-muted">
        命中用户或账号时自动展开并高亮关键词；账号可按登录标识与平台姓名匹配。
      </p>
    </div>

    <!-- 树体 -->
    <div class="xb-scroll min-h-0 flex-1 overflow-y-auto p-2" style="scrollbar-gutter: stable">
      <!-- 加载中 -->
      <div v-if="loadingTree" class="space-y-2 p-1.5">
        <div v-for="i in 5" :key="i" class="flex items-center gap-2.5">
          <div class="h-8 w-8 shrink-0 rounded-full bg-ink/5 animate-pulse" />
          <div class="flex-1 space-y-1.5">
            <div class="h-3 w-24 rounded bg-ink/5 animate-pulse" />
            <div class="h-2.5 w-16 rounded bg-ink/5 animate-pulse" />
          </div>
        </div>
      </div>

      <!-- 加载失败 -->
      <div v-else-if="treeError" class="flex flex-col items-center gap-2 px-4 py-10 text-center text-ink-muted">
        <Icon name="x-circle" :size="26" class="text-danger opacity-70" />
        <span class="text-xs">{{ treeError }}</span>
        <button
          type="button"
          class="rounded-lg border border-ink/10 px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:bg-cloud"
          @click="loadTree"
        >重试</button>
      </div>

      <!-- 全站无账号 -->
      <div v-else-if="tree.length === 0" class="flex flex-col items-center gap-2 px-4 py-10 text-center text-ink-muted">
        <Icon name="users" :size="26" class="opacity-40" />
        <span class="text-xs">全站还没有任何 B 平台账号</span>
      </div>

      <!-- 搜索无命中 -->
      <div v-else-if="filteredTree.length === 0" class="flex flex-col items-center gap-1.5 px-4 py-10 text-center text-ink-muted">
        <Icon name="search" :size="24" class="opacity-40" />
        <span class="text-xs">没有匹配的用户或账号，换个关键词试试</span>
      </div>

      <template v-else>
        <div v-for="node in filteredTree" :key="node.id" class="mb-0.5">
          <!-- 用户根节点 -->
          <button
            type="button"
            class="flex w-full items-center gap-2 rounded-xl px-2 py-2 text-left transition hover:bg-cloud"
            :aria-expanded="isOpen(node)"
            @click="toggleNode(node.id)"
          >
            <Icon
              name="chevron-right"
              :size="14"
              class="shrink-0 text-ink-muted transition-transform duration-200"
              :class="isOpen(node) ? 'rotate-90' : ''"
            />
            <span
              class="grid h-8 w-8 shrink-0 place-items-center rounded-full text-[12.5px] font-semibold"
              :class="avatarCls(node)"
            >{{ node.username.charAt(0).toUpperCase() }}</span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-[13.5px] font-semibold text-ink" v-html="highlight(node.username, node.userHit)"></span>
              <span class="mt-0.5 block text-[11px] text-ink-muted">
                {{ node.role === 'admin' ? '管理员' : '普通用户' }}{{ node.enabled ? '' : ' · 已禁用' }}
              </span>
            </span>
            <span class="shrink-0 rounded-full bg-cloud px-2 py-0.5 text-[11px] text-ink-muted tabular-nums">
              {{ node.accounts.length }} 账号
            </span>
          </button>

          <!-- B 平台账号子节点 -->
          <div v-if="isOpen(node)" class="relative ml-[26px] space-y-0.5 border-l border-ink/10 pb-1 pl-2.5">
            <button
              v-for="a in node.accounts"
              :key="a.id"
              type="button"
              class="relative flex w-full items-center gap-2 rounded-xl px-2 py-1.5 text-left transition hover:bg-cloud"
              :class="selectedAccountId === Number(a.id) ? 'bg-brand/[0.08] outline outline-1 outline-brand/30' : ''"
              @click="selectAccount(Number(a.id))"
            >
              <span class="h-2 w-2 shrink-0 rounded-full" :class="dotCls(a)" :title="dotTitle(a)" />
              <span class="min-w-0 flex-1">
                <span class="flex items-center gap-1.5">
                  <span class="truncate text-[13px] font-medium text-ink">{{ a.account }}</span>
                  <span
                    class="shrink-0 rounded-full px-1.5 py-px text-[10px] font-medium"
                    :class="typeBadge(a.type).cls"
                  >{{ typeBadge(a.type).label }}</span>
                </span>
                <span class="mt-px block truncate text-[11px] text-ink-muted">
                  {{ (a.profile && a.profile.name) || '未回填姓名' }} · {{ lastText(a) }}
                </span>
              </span>
            </button>
            <p v-if="node.accounts.length === 0" class="px-2 py-1.5 text-[11.5px] text-ink-muted">该用户尚未添加 B 平台账号</p>
          </div>
        </div>
      </template>
    </div>

    <!-- 图例 -->
    <div class="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 border-t border-ink/5 px-4 py-2.5 text-[11px] text-ink-muted">
      <span class="inline-flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-success" />最近成功</span>
      <span class="inline-flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-danger" />最近失败</span>
      <span class="inline-flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-ink/20" />凭证失效</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useSiteRecordsStore } from '@/stores/siteRecords'
import Icon from '@/components/Icon.vue'

const store = useSiteRecordsStore()
const { keyword, filteredTree, tree, treeCounts, loadingTree, treeError, selectedAccountId } = storeToRefs(store)
const { loadTree, selectAccount, accDot } = store

// 展开状态：本地维护（有关键词时强制全开，清空后回到本地状态）
const expanded = ref(new Set())
function isOpen(node) {
  if (keyword.value.trim()) return true
  return expanded.value.has(node.id)
}
function toggleNode(id) {
  const next = new Set(expanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expanded.value = next
}

// 头像配色：按用户 id 稳定散列到四套柔和底色，列表扫读时可区分
const AVATAR_CLS = [
  'bg-brand/10 text-brand',
  'bg-success/10 text-success',
  'bg-violet-500/10 text-violet-600',
  'bg-amber/15 text-amber',
]
function avatarCls(node) {
  return AVATAR_CLS[Math.abs(node.id) % AVATAR_CLS.length]
}

function dotCls(a) {
  const dot = accDot(a)
  return dot === 'ok' ? 'bg-success' : dot === 'err' ? 'bg-danger' : 'bg-ink/20'
}
function dotTitle(a) {
  const dot = accDot(a)
  return dot === 'ok' ? '最近签到成功' : dot === 'err' ? '最近签到失败' : '凭证失效或未校验'
}

function typeBadge(t) {
  if (t === 'activity') return { label: '活动', cls: 'bg-info/10 text-info' }
  if (t === 'dorm') return { label: '寝室', cls: 'bg-brand/10 text-brand' }
  return { label: '通用', cls: 'bg-ink/5 text-ink-soft' }
}

function lastText(a) {
  const ls = a.lastSignIn || {}
  if (!ls.time || ls.status === 'never') return '暂无签到记录'
  const label = ls.status === 'fail' ? '最近失败' : ls.status === 'skip' ? '最近跳过' : '最近成功'
  return `${label} ${ls.time}`
}

// 搜索命中高亮：plain 文本按关键词切片包 <mark>；未命中原样返回
function highlight(text, hit) {
  const raw = String(text ?? '')
  const q = keyword.value.trim()
  if (!hit || !q) return raw
  const idx = raw.toLowerCase().indexOf(q.toLowerCase())
  if (idx < 0) return raw
  return `${raw.slice(0, idx)}<mark class="rounded bg-amber/30 px-0.5">${raw.slice(idx, idx + q.length)}</mark>${raw.slice(idx + q.length)}`
}
</script>
