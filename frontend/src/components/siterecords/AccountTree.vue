<template>
  <div class="flex min-h-0 flex-col overflow-hidden rounded-2xl">
    <!-- 头部：标题 + 计数 + 模糊搜索 -->
    <div class="shrink-0 border-b border-ink/5 px-4 pb-3 pt-4">
      <div class="flex items-baseline gap-2">
        <h3 class="text-sm font-semibold text-ink">账号树</h3>
        <span class="text-[11.5px] tabular-nums text-ink-muted">{{ treeCounts.users }} 位用户 · {{ treeCounts.accounts }} 个账号</span>
      </div>
      <div class="mt-2.5 flex items-center gap-2 rounded-xl bg-cloud/60 px-3 py-2 ring-1 ring-inset ring-ink/5 transition focus-within:bg-elevated focus-within:ring-2 focus-within:ring-brand/30">
        <Icon name="search" :size="15" class="shrink-0 text-ink-muted" />
        <input
          :value="keyword"
          type="text"
          placeholder="搜索用户名 / B 平台账号…"
          aria-label="搜索用户名或 B 平台账号"
          class="min-w-0 flex-1 bg-transparent text-[13px] text-ink outline-none placeholder:text-ink-muted"
          @input="keyword = $event.target.value"
        />
        <button
          v-if="keyword"
          type="button"
          class="grid h-5 w-5 shrink-0 place-items-center rounded-md text-ink-muted transition hover:bg-cloud hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
          aria-label="清除搜索"
          @click="keyword = ''"
        >
          <Icon name="close" :size="13" />
        </button>
      </div>
    </div>

    <!-- 树体 -->
    <div class="xb-scroll min-h-0 flex-1 overflow-y-auto p-2" style="scrollbar-gutter: stable">
      <!-- 加载中 -->
      <div v-if="loadingTree" class="space-y-2 p-1.5">
        <div v-for="i in 5" :key="i" class="flex items-center gap-2.5">
          <div class="xb-skel h-8 w-8 shrink-0 rounded-full bg-ink/5 animate-pulse" />
          <div class="flex-1 space-y-1.5">
            <div class="xb-skel h-3 w-24 rounded bg-ink/5 animate-pulse" />
            <div class="xb-skel h-2.5 w-16 rounded bg-ink/5 animate-pulse" />
          </div>
        </div>
      </div>

      <!-- 加载失败 -->
      <div v-else-if="treeError" class="flex flex-col items-center gap-2.5 px-4 py-10 text-center text-ink-muted">
        <span class="grid h-11 w-11 place-items-center rounded-2xl bg-danger/10">
          <Icon name="x-circle" :size="20" class="text-danger" />
        </span>
        <span class="text-xs">{{ treeError }}</span>
        <button
          type="button"
          class="rounded-lg border border-ink/10 px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:bg-cloud focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
          @click="loadTree"
        >重试</button>
      </div>

      <!-- 全站无账号 -->
      <div v-else-if="tree.length === 0" class="flex flex-col items-center gap-2.5 px-4 py-10 text-center text-ink-muted">
        <span class="grid h-11 w-11 place-items-center rounded-2xl bg-cloud">
          <Icon name="users" :size="20" class="opacity-60" />
        </span>
        <span class="text-xs">全站还没有任何 B 平台账号</span>
      </div>

      <!-- 搜索无命中 -->
      <div v-else-if="filteredTree.length === 0" class="flex flex-col items-center gap-2.5 px-4 py-10 text-center text-ink-muted">
        <span class="grid h-11 w-11 place-items-center rounded-2xl bg-cloud">
          <Icon name="search" :size="20" class="opacity-60" />
        </span>
        <span class="text-xs">没有匹配的用户或账号，换个关键词试试</span>
      </div>

      <template v-else>
        <div v-for="node in filteredTree" :key="node.id" class="mb-0.5">
          <!-- 用户根节点 -->
          <button
            type="button"
            class="flex w-full items-center gap-2 rounded-xl px-2 py-2 text-left transition hover:bg-cloud/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
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
              class="grid h-8 w-8 shrink-0 place-items-center rounded-full text-[12.5px] font-semibold ring-1 ring-inset ring-ink/5"
              :class="avatarCls(node)"
            >{{ node.username.charAt(0).toUpperCase() }}</span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-[13.5px] font-semibold text-ink" v-html="highlight(node.username, node.userHit)"></span>
              <span class="mt-0.5 block text-[11px] text-ink-muted">
                {{ node.role === 'admin' ? '管理员' : '普通用户' }}{{ node.enabled ? '' : ' · 已禁用' }}
              </span>
            </span>
            <span class="shrink-0 text-[11px] tabular-nums text-ink-muted">{{ node.accounts.length }} 账号</span>
          </button>

          <!-- B 平台账号子节点 -->
          <div v-if="isOpen(node)" class="relative ml-[26px] space-y-0.5 border-l border-ink/10 pb-1 pl-2.5">
            <button
              v-for="a in node.accounts"
              :key="a.id"
              type="button"
              class="relative flex w-full items-center gap-2 rounded-xl px-2 py-1.5 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
              :class="selectedAccountId === Number(a.id) ? 'bg-brand/[0.07]' : 'hover:bg-cloud/70'"
              @click="selectAccount(Number(a.id))"
            >
              <!-- 选中态由树连接线本身表达：该行的连线段落转品牌色 -->
              <span
                v-if="selectedAccountId === Number(a.id)"
                class="pointer-events-none absolute inset-y-1 -left-2.5 w-[2px] rounded-full bg-brand"
                aria-hidden="true"
              />
              <span class="h-2 w-2 shrink-0 rounded-full" :class="dotCls(a)" :title="dotTitle(a)" />
              <span class="min-w-0 flex-1">
                <span class="flex items-center gap-1.5">
                  <span class="truncate text-[13px] font-medium text-ink">{{ a.account }}</span>
                  <span
                    class="shrink-0 rounded-md px-1.5 py-px text-[10px] font-medium"
                    :class="accountTypeMeta(a.signTasks).cls"
                  >{{ accountTypeMeta(a.signTasks).label }}</span>
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
    <div class="flex shrink-0 flex-wrap items-center gap-x-3.5 gap-y-1 border-t border-ink/5 px-4 py-2.5 text-[10.5px] text-ink-muted">
      <span class="inline-flex items-center gap-1.5"><span class="h-1.5 w-1.5 rounded-full bg-success" aria-hidden="true" />最近成功</span>
      <span class="inline-flex items-center gap-1.5"><span class="h-1.5 w-1.5 rounded-full bg-danger" aria-hidden="true" />最近失败</span>
      <span class="inline-flex items-center gap-1.5"><span class="h-1.5 w-1.5 rounded-full bg-ink/20" aria-hidden="true" />凭证失效</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useSiteRecordsStore } from '@/stores/siteRecords'
import { accountTypeMeta } from '@/utils/accountType'
import { highlightText } from '@/utils/text'
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

// 头像配色：按用户 id 稳定散列到四套柔和底色，列表扫读时可区分。
// 四套都走语义令牌——默认调色板的 violet-600 在浅底 5.04 达标、深底只有 1.86，
// 而一个色值不可能两态都达标（同 text-brand 的拆档问题），交给明暗轴换值最省事。
const AVATAR_CLS = [
  'bg-brand/10 text-brand',
  'bg-success/10 text-success',
  'bg-info/10 text-info',
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

function lastText(a) {
  const ls = a.lastSignIn || {}
  if (!ls.time || ls.status === 'never') return '暂无签到记录'
  const label = ls.status === 'fail' ? '最近失败' : ls.status === 'skip' ? '最近跳过' : '最近成功'
  return `${label} ${ls.time}`
}

// 搜索命中高亮：先 HTML 转义再拼接 mark —— 用户名/账号均可由用户侧决定，
// 直接 v-html 原文等于开注入口子。escapeHtml/highlightText 唯一出处 utils/text.js
// （与 UserManagementView 同一套）。mark 样式保持本页原样（无 text-ink）。
function highlight(text, hit) {
  return highlightText(text, hit ? keyword.value : '', 'rounded bg-amber/30 px-0.5')
}
</script>

<style scoped>
/* 仅让刷新/骨架脉冲等动画保留，减弱动效偏好下退化为静态 */
@media (prefers-reduced-motion: reduce) {
  .xb-skel { animation: none; }
}
</style>
