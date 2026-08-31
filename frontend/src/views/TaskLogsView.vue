<template>
  <div class="flex flex-col gap-6 lg:flex-1 lg:min-h-0">
    <RefreshStrip v-if="refreshingLogs" />
    <!-- 概览：总执行 / 成功 / 失败 / 跳过 -->
    <div class="grid shrink-0 grid-cols-2 gap-4 lg:grid-cols-4">
      <StatCard
        label="总执行"
        :value="overview.total"
        unit="项"
        icon="records"
        tone="brand"
        :loading="loadingLogs"
        :count-up
      />
      <StatCard
        label="成功"
        :value="overview.success"
        unit="项"
        icon="check-circle"
        tone="success"
        :loading="loadingLogs"
        :count-up
      />
      <StatCard
        label="失败"
        :value="overview.fail"
        unit="项"
        icon="x-circle"
        tone="danger"
        :loading="loadingLogs"
        :count-up
      />
      <StatCard
        label="跳过"
        :value="overview.skip"
        unit="项"
        icon="alert"
        tone="amber"
        :loading="loadingLogs"
        :count-up
      />
    </div>

    <!-- 筛选条：账号决定归属；类型/状态双胶囊竖线分隔 -->
    <div class="dash-card fade-up relative z-30 shrink-0 p-3 sm:p-4">
      <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
        <div class="flex items-center gap-2">
          <span class="shrink-0 text-sm font-medium text-ink-soft"
            >平台账号</span
          >
          <div class="w-44 sm:w-56">
            <BaseSelect
              :model-value="selectedAccountId"
              :options="accountFilterOptions"
              :searchable="true"
              :disabled="loadingAccounts"
              placeholder="选择账号"
              size="sm"
              @update:model-value="store.selectAccount"
            />
          </div>
        </div>
        <div class="ml-auto flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-xl border border-ink/10 bg-white px-3 py-1.5 text-sm font-medium text-ink-soft transition hover:border-danger/30 hover:text-danger"
            @click="openPurge"
          >
            <Icon name="trash" :size="14" />
            清空我的日志
          </button>
          <div class="inline-flex items-center gap-1 rounded-xl bg-cloud p-1">
            <span class="px-1.5 text-[11px] font-medium text-ink-muted"
              >类型</span
            >
            <button
              v-for="t in typeTabs"
              :key="`ty-${t.value}`"
              type="button"
              class="whitespace-nowrap rounded-lg px-2.5 py-1.5 text-sm font-medium transition"
              :class="
                typeFilter === t.value
                  ? 'bg-white text-brand shadow-sm'
                  : 'text-ink-muted hover:text-ink-soft'
              "
              @click="store.setType(t.value)"
            >
              {{ t.label }}
            </button>
          </div>
          <span class="h-5 w-px bg-ink/10" aria-hidden="true" />
          <div class="inline-flex items-center gap-1 rounded-xl bg-cloud p-1">
            <span class="px-1.5 text-[11px] font-medium text-ink-muted"
              >状态</span
            >
            <button
              v-for="s in statusTabs"
              :key="`st-${s.value}`"
              type="button"
              class="whitespace-nowrap rounded-lg px-2.5 py-1.5 text-sm font-medium transition"
              :class="
                statusFilter === s.value
                  ? 'bg-white text-brand shadow-sm'
                  : 'text-ink-muted hover:text-ink-soft'
              "
              @click="store.setStatus(s.value)"
            >
              {{ s.label }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 清空我的日志：确认弹窗（必须指定 before 上限，防误清空全部历史） -->
    <Transition name="fade">
      <div
        v-if="purgeOpen"
        class="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 px-4"
        @click.self="closePurge"
      >
        <div class="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl">
          <h3 class="text-base font-semibold text-ink">清空我的执行日志</h3>
          <p class="mt-1.5 text-sm leading-relaxed text-ink-muted">
            将删除你名下、<span class="font-medium text-ink-soft">该日期之前</span>的全部执行日志（不可恢复）。系统仍会按保留策略自动清理更早记录。
          </p>
          <label class="mt-3 block text-xs font-medium text-ink-muted">删除此日期之前的日志</label>
          <input
            v-model="purgeBefore"
            type="date"
            class="login-input mt-1 w-full px-3 py-2 text-sm"
          />
          <div class="mt-4 flex justify-end gap-2">
            <button
              type="button"
              class="rounded-xl px-3.5 py-2 text-sm font-medium text-ink-muted transition hover:text-ink-soft"
              @click="closePurge"
            >
              取消
            </button>
            <button
              type="button"
              class="rounded-xl bg-danger px-3.5 py-2 text-sm font-semibold text-white shadow-lg shadow-danger/25 transition hover:bg-danger/90 disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="!purgeBefore || purging"
              @click="confirmPurge"
            >
              {{ purging ? '清理中…' : '确认清空' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 平铺列表：按执行时间倒序，状态色条为纵向扫读锚点；列表固定高度内部滚动，分页常驻底部。
         min-h-[480px] 给列表卡片一个舒适下限（与 SignRecordsView 一致），短屏不至过矮、长屏仍随 flex-1 撑满。
         静默刷新期旧日志原地保留，仅整卡降透明并暂停交互（筛选/翻页/删除不再闪加载页） -->
    <div
      class="dash-card fade-up flex flex-col rounded-2xl transition-opacity lg:min-h-[480px] lg:flex-1"
      :class="refreshingLogs && 'opacity-60 pointer-events-none'"
    >
      <div class="lg:flex-1 lg:min-h-0 lg:overflow-y-auto">
      <ul v-if="loadingLogs" class="divide-y divide-ink/5">
        <li
          v-for="n in 6"
          :key="n"
          class="flex items-stretch gap-3 px-3 py-3 sm:px-4"
        >
          <span class="w-1 shrink-0 rounded-full bg-ink/5" />
          <div class="min-w-0 flex-1 space-y-2">
            <div class="flex items-center gap-2">
              <div class="h-4 w-28 rounded bg-ink/5 animate-pulse" />
              <div class="h-4 w-16 rounded-full bg-ink/5 animate-pulse" />
            </div>
            <div class="h-3 w-3/4 rounded bg-ink/5 animate-pulse" />
            <div class="h-3 w-40 rounded bg-ink/5 animate-pulse" />
          </div>
          <div
            class="h-6 w-14 shrink-0 self-center rounded-full bg-ink/5 animate-pulse"
          />
        </li>
      </ul>
      <div
        v-else-if="logs.length === 0"
        class="flex min-h-[360px] flex-col items-center justify-center gap-3 py-6 text-ink-muted"
      >
        <Icon name="records" :size="36" class="opacity-40" />
        <p class="text-sm font-medium text-ink-soft">暂无执行日志</p>
        <p class="text-xs">当前筛选条件下还没有任务执行记录</p>
      </div>
      <ul v-else class="divide-y divide-ink/5">
        <li
          v-for="row in logs"
          :key="row.id"
          class="transition hover:bg-cloud/40"
        >
          <div class="flex items-stretch gap-3 px-3 py-3 sm:px-4">
            <!-- 行主体点击展开；删除键与其同级，故不会误触发展开 -->
            <button
              type="button"
              class="flex min-w-0 flex-1 items-stretch gap-3 text-left"
              :aria-expanded="store.isOpen(row.id)"
              @click="store.toggleDetail(row)"
            >
              <span
                class="w-1 shrink-0 rounded-full"
                :class="logRail(row.status)"
              />

              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="truncate text-[15px] font-semibold text-ink">{{
                    row.studentName || row.accountName
                  }}</span>
                  <span v-if="row.college" class="truncate text-xs text-ink-muted">
                    · {{ row.college
                    }}<template v-if="row.major"> · {{ row.major }}</template>
                  </span>
                  <span
                    class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap"
                    :class="typeBadge(row.taskType).cls"
                  >
                    {{ typeBadge(row.taskType).label }}
                  </span>
                </div>
                <div class="mt-1 truncate text-sm text-ink-soft">
                  {{ row.taskName }}
                </div>
                <div
                  class="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted"
                >
                  <span class="tabular-nums">{{
                    row.createdAt || row.signDate
                  }}</span>
                  <span>{{
                    row.initiator === "manual" ? "手动触发" : "系统触发"
                  }}</span>
                  <span class="text-ink-muted/80">{{
                    store.isOpen(row.id) ? "收起配置" : "查看配置"
                  }}</span>
                </div>
                <div
                  v-if="
                    (row.status === 'fail' || row.status === 'skip') &&
                    row.failReason
                  "
                  class="mt-1.5 flex items-start gap-1.5 rounded-lg px-2.5 py-1.5 text-xs"
                  :class="
                    row.status === 'fail'
                      ? 'bg-danger/[0.04] text-danger'
                      : 'bg-amber/[0.06] text-amber'
                  "
                >
                  <Icon
                    :name="row.status === 'fail' ? 'x-circle' : 'alert'"
                    :size="13"
                    class="mt-0.5 shrink-0"
                  />
                  <span>{{ row.failReason }}</span>
                </div>
              </div>

              <span
                class="inline-flex shrink-0 items-center gap-1.5 self-center rounded-full px-2.5 py-1 text-xs font-medium whitespace-nowrap"
                :class="logPill(row.status).cls"
              >
                <span
                  class="h-1.5 w-1.5 rounded-full"
                  :class="logPill(row.status).dot"
                />
                {{ logPill(row.status).label }}
              </span>

              <Icon
                name="chevron-right"
                :size="18"
                class="shrink-0 self-center text-ink-muted transition-[transform,color] duration-300"
                :class="store.isOpen(row.id) ? 'rotate-90 text-brand' : ''"
              />
            </button>

            <button
              type="button"
              class="shrink-0 self-center rounded-lg p-1.5 text-ink-muted transition hover:bg-danger/[0.06] hover:text-danger"
              title="删除该条日志"
              @click="onDelete(row)"
            >
              <Icon name="trash" :size="14" />
            </button>
          </div>

          <!-- 展开详情：该日志所属任务执行时采用的完整配置（手风琴：展开另一条会自动收起本条） -->
          <Transition :css="false" @enter="onDetailEnter" @leave="onDetailLeave">
            <div
              v-if="store.isOpen(row.id)"
              class="overflow-hidden border-t border-ink/5 bg-cloud/30 px-3 py-4 sm:px-5"
            >
              <template v-if="detailOf(row) && detailOf(row).loading">
                <div class="flex items-center justify-center py-8 text-sm text-ink-muted">
                  加载配置详情中…
                </div>
              </template>

              <div
                v-else-if="detailOf(row) && detailOf(row).error"
                class="py-2 text-sm text-danger"
              >
                {{ detailOf(row).error }}
              </div>

              <div v-else-if="configOf(row) && configOf(row).hasSnapshot" class="space-y-3">
                <!-- 配置来源：模式 + 配置套名称 + 口径提示 -->
                <div
                  data-detail-item
                  class="flex flex-wrap items-center gap-2 rounded-xl bg-white/70 px-3 py-2.5"
                >
                  <span
                    class="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
                    :class="modeBadge(configOf(row).mode).cls"
                  >
                    <Icon :name="modeBadge(configOf(row).mode).icon" :size="12" />
                    {{ configOf(row).modeLabel }}
                  </span>
                  <span v-if="configOf(row).configSetName" class="truncate text-xs text-ink-soft">
                    来自配置套
                    <b class="font-medium text-ink">{{ configOf(row).configSetName }}</b>
                  </span>
                  <span v-else class="truncate text-xs text-ink-soft">
                    任务自持配置，不随配置套变动
                  </span>
                  <span
                    class="ml-auto inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald/10 px-2 py-0.5 text-[11px] text-emerald"
                  >
                    <Icon name="clock" :size="11" />执行时配置快照
                  </span>
                </div>

                <!-- 配置分区：时间 / 位置 / 图库 / 推送 / 备注 / 其它 -->
                <div class="grid gap-3 lg:grid-cols-2">
                  <section
                    v-for="s in detailSections(configOf(row))"
                    :key="s.key"
                    data-detail-item
                    class="rounded-xl border border-ink/5 bg-white p-3"
                  >
                    <h4
                      class="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-muted"
                    >
                      <Icon :name="s.icon" :size="12" />{{ s.title }}
                    </h4>

                    <!-- 名称类长文本：整行展示，避免挤进两列被截断 -->
                    <p
                      v-if="s.note"
                      class="mt-2 truncate text-xs font-medium text-ink"
                      :title="s.note"
                    >
                      {{ s.note }}
                    </p>

                    <!-- 标签组：推送通道 / 签到备注 -->
                    <div v-if="s.chips && s.chips.length" class="mt-2 flex flex-wrap gap-1.5">
                      <span
                        v-for="(c, ci) in s.chips"
                        :key="ci"
                        class="inline-flex max-w-full items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium"
                        :class="c.tone"
                      >
                        <span class="truncate">{{ c.label }}</span>
                        <span v-if="c.hint" class="truncate opacity-70">· {{ c.hint }}</span>
                      </span>
                    </div>
                    <p
                      v-else-if="s.chips"
                      class="mt-2 rounded-lg bg-cloud/60 px-2.5 py-2 text-xs text-ink-muted"
                    >
                      {{ s.emptyText }}
                    </p>

                    <!-- 键值网格 -->
                    <div v-if="s.fields" class="mt-2 grid grid-cols-2 gap-2">
                      <div
                        v-for="f in s.fields"
                        :key="f.label"
                        class="rounded-lg bg-cloud/50 px-2.5 py-1.5"
                        :class="f.span === 2 ? 'col-span-2' : ''"
                      >
                        <p class="text-[11px] text-ink-muted">{{ f.label }}</p>
                        <p
                          class="mt-0.5 truncate text-xs font-medium text-ink"
                          :class="f.mono ? 'tabular-nums' : ''"
                          :title="f.value"
                        >
                          {{ f.value }}
                        </p>
                      </div>
                    </div>
                  </section>
                </div>
              </div>
              <div v-else-if="configOf(row)" class="py-7 text-center">
                <p class="text-sm text-ink-muted">无配置快照</p>
                <p class="mt-1 text-xs text-ink-muted/80">
                  该记录执行时未保存配置快照（升级前的历史日志）。
                </p>
              </div>
            </div>
          </Transition>
        </li>
      </ul>
      </div>

      <div
        v-if="total > 0"
        class="shrink-0 border-t border-ink/10 px-4 py-2.5 sm:px-5"
      >
        <BasePagination
          :page="page"
          :page-size="pageSize"
          :total="total"
          :page-size-options="[10, 20, 50]"
          @update:page="store.setPage"
          @update:page-size="store.setPageSize"
        />
      </div>
    </div>

    <div class="h-6 shrink-0" aria-hidden="true" />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute } from "vue-router";
import { storeToRefs } from "pinia";
import { gsap } from "gsap";
import { useTaskLogsStore } from "@/stores/taskLogs";
import { toast } from "@/utils/toast";
import Icon from "@/components/Icon.vue";
import BaseSelect from "@/components/BaseSelect.vue";
import StatCard from "@/components/StatCard.vue";
import BasePagination from "@/components/BasePagination.vue";
import RefreshStrip from '@/components/RefreshStrip.vue'

const store = useTaskLogsStore();
const route = useRoute();
const {
  selectedAccountId,
  loadingAccounts,
  typeFilter,
  statusFilter,
  page,
  pageSize,
  logs,
  total,
  overview,
  loadingLogs,
  refreshingLogs,
  accountOptions,
} = storeToRefs(store);

// ===== 自助删除：单条删除 + 「清空我的日志」确认弹窗 =====
const purgeOpen = ref(false);
const purgeBefore = ref("");
const purging = ref(false);

function openPurge() {
  purgeBefore.value = "";
  purgeOpen.value = true;
}
function closePurge() {
  if (purging.value) return;
  purgeOpen.value = false;
}
async function confirmPurge() {
  if (!purgeBefore.value) return;
  purging.value = true;
  try {
    const res = await store.purgeBefore(purgeBefore.value, {
      accountId: selectedAccountId.value || "",
      type: typeFilter.value,
      status: statusFilter.value,
    });
    toast(`已清理 ${res.deleted ?? 0} 条日志`, "success");
    purgeOpen.value = false;
  } catch (e) {
    toast(e.message || "清理失败", "error");
  } finally {
    purging.value = false;
  }
}
async function onDelete(row) {
  try {
    await store.removeLog(row.id);
    toast("已删除该条日志", "success");
  } catch (e) {
    toast(e.message || "删除失败", "error");
  }
}

// 筛选器额外加「全部账号」选项（value=null）
const accountFilterOptions = computed(() => [
  { value: null, label: "全部账号" },
  ...accountOptions.value,
]);

const typeTabs = [
  { label: "全部", value: "all" },
  { label: "寝室签到", value: "dorm" },
  { label: "活动签到", value: "activity" },
];
const statusTabs = [
  { label: "全部", value: "all" },
  { label: "成功", value: "success" },
  { label: "失败", value: "fail" },
  { label: "跳过", value: "skip" },
];

function typeBadge(t) {
  return t === "activity"
    ? { label: "活动签到", cls: "bg-info/10 text-info" }
    : { label: "寝室签到", cls: "bg-brand/10 text-brand" };
}

function logRail(status) {
  if (status === "success") return "bg-success";
  if (status === "fail") return "bg-danger";
  return "bg-amber";
}

function logPill(status) {
  if (status === "success")
    return {
      label: "成功",
      cls: "bg-success/10 text-success",
      dot: "bg-success",
    };
  if (status === "fail")
    return { label: "失败", cls: "bg-danger/10 text-danger", dot: "bg-danger" };
  return { label: "跳过", cls: "bg-amber/10 text-amber", dot: "bg-amber" };
}

// ===== 展开详情：配置分区渲染 =====
// 后端已把 locationId / groupId / credIds 等 id 解析为可读名称，此处只做展示层排版
const NOTIFY_LABELS = { success: "成功", skip: "跳过", fail: "失败" };
const TEMPLATE_LABELS = {
  html: "HTML 卡片",
  txt: "纯文本",
  markdown: "Markdown",
};
// 与凭证池一致的通道配色，避免同一通道在两处颜色打架
const CHANNEL_TONE = {
  serverchan: "bg-brand/10 text-brand",
  pushplus: "bg-success/10 text-success",
  email: "bg-info/10 text-info",
};

function modeBadge(mode) {
  if (mode === "follow")
    return { icon: "layers", cls: "bg-brand/10 text-brand" };
  if (mode === "custom")
    return { icon: "sliders", cls: "bg-ink/10 text-ink-soft" };
  return { icon: "box", cls: "bg-success/10 text-success" }; // standalone
}

// 逐行读取：手风琴收起动画期间旧节点仍在 DOM，按行取自己那份缓存可避免串到新展开项的数据
function detailOf(row) {
  return store.detailOf(row.id);
}

function configOf(row) {
  const d = store.detailOf(row.id);
  return d && d.data ? d.data : null;
}

function detailSections(d) {
  if (!d) return [];
  const t = d.time || {};
  const loc = d.location;
  const img = d.image || {};
  const push = d.push || {};
  const adv = d.advanced || {};
  const notify = push.notify || {};
  const notifyOn = ["success", "skip", "fail"]
    .filter((k) => notify[k])
    .map((k) => NOTIFY_LABELS[k]);
  const channels = push.channels || [];

  return [
    {
      key: "time",
      title: "执行时间",
      icon: "clock",
      fields: [
        { label: "签到时刻", value: t.signTime || "—", mono: true },
        { label: "重复", value: t.weekdayLabel || "—" },
        { label: "允许时段", value: t.window || "—", mono: true },
        {
          label: "随机延迟",
          value: t.randomDelayMax ? `≤ ${t.randomDelayMax} 分钟` : "关闭",
        },
      ],
    },
    {
      key: "location",
      title: "签到位置",
      icon: "map-pin",
      note: loc ? loc.name : "",
      fields: loc
        ? [
            { label: "经纬度", value: `${loc.lng}, ${loc.lat}`, mono: true },
            { label: "抖动半径", value: `${loc.offsetM} 米` },
            { label: "地址", value: loc.address || "—", span: 2 },
          ]
        : [{ label: "状态", value: "未配置，回退任务围栏中心", span: 2 }],
    },
    {
      key: "image",
      title: "图库",
      icon: "image",
      fields: [
        { label: "状态", value: img.enabled ? "已启用" : "未启用" },
        { label: "用后策略", value: img.strategyLabel || "—" },
        { label: "取图范围", value: img.groupName || "全部图片", span: 2 },
      ],
    },
    {
      key: "push",
      title: "结果推送",
      icon: "bell",
      chips: channels.map((c) => ({
        label: c.label,
        hint: c.credentialName,
        tone: CHANNEL_TONE[c.key] || "bg-ink/10 text-ink-soft",
      })),
      emptyText: "未配置推送通道",
      fields: channels.length
        ? [
            {
              label: "内容模板",
              value: TEMPLATE_LABELS[push.template] || push.template || "—",
            },
            {
              label: "凭证来源",
              value: push.useOwnCredential ? "资源池凭证" : "直接填写",
            },
            {
              label: "通知时机",
              value: notifyOn.length ? notifyOn.join(" / ") : "全部关闭",
              span: 2,
            },
          ]
        : null,
    },
    {
      key: "remarks",
      title: "签到备注",
      icon: "file",
      chips: (d.remarks || []).map((r) => ({
        label: r,
        tone: "bg-cloud text-ink-soft",
      })),
      emptyText: "未配置备注",
    },
    {
      key: "other",
      title: "其它",
      icon: "settings",
      fields: [
        {
          label: "围栏拦截",
          value: (d.fence || {}).intercept === false ? "已关闭" : "开启",
        },
        {
          label: "请求 UA",
          value: adv.uaTemplateName || (adv.customUa ? "自定义" : "平台默认"),
        },
      ],
    },
  ];
}

// ===== 展开/收起动画（GSAP）=====
// 高度与纵向 padding 必须同步补间，且收起时显式量出「去 padding 的纯内容高度」再归零，
// 否则 height:auto 末态量算不稳、padding 残留会导致收起后留白或跳动。
const reduceMotion = ref(false);
let mm = null;

// 量出纯内容高度：border-box 下 offsetHeight 含 padding，故临时把纵向 padding 归零再量
function measureContent(el) {
  const cs = getComputedStyle(el);
  const pt = parseFloat(cs.paddingTop) || 0;
  const pb = parseFloat(cs.paddingBottom) || 0;
  const prevT = el.style.paddingTop;
  const prevB = el.style.paddingBottom;
  el.style.paddingTop = "0px";
  el.style.paddingBottom = "0px";
  const h = el.offsetHeight;
  el.style.paddingTop = prevT;
  el.style.paddingBottom = prevB;
  return { h, pt, pb };
}

function onDetailEnter(el, done) {
  if (reduceMotion.value) {
    done();
    return;
  }
  // 锁定裁剪 + 合成层，避免展开过程中内容溢出/重排抖动
  gsap.set(el, { overflow: "hidden", willChange: "height, padding" });
  const { h, pt, pb } = measureContent(el);
  gsap.fromTo(
    el,
    { height: 0, paddingTop: 0, paddingBottom: 0, autoAlpha: 0 },
    {
      height: h,
      paddingTop: pt,
      paddingBottom: pb,
      autoAlpha: 1,
      duration: 0.34,
      ease: "power2.out",
      onComplete: () => {
        // 展开结束清掉内联 height/padding，让内容后续变化（如窗口缩放）能自然撑开
        gsap.set(el, { clearProps: "height, paddingTop, paddingBottom, overflow, willChange" });
        done();
      },
    }
  );
  // 分区错峰落位：容器展开之后再逐块淡入，避免整块内容一次性闪现
  const items = el.querySelectorAll("[data-detail-item]");
  if (items.length) {
    gsap.fromTo(
      items,
      { autoAlpha: 0, y: 8 },
      {
        autoAlpha: 1,
        y: 0,
        duration: 0.3,
        stagger: 0.05,
        delay: 0.12,
        ease: "power2.out",
        overwrite: true,
        clearProps: "opacity,transform",
      }
    );
  }
}

function onDetailLeave(el, done) {
  if (reduceMotion.value) {
    done();
    return;
  }
  gsap.set(el, { overflow: "hidden", willChange: "height, padding" });
  const { h, pt, pb } = measureContent(el);
  // 高度与 padding 一起从当前值平滑归零；power2.inOut 让收起缓入缓出，比单边 in 更顺
  gsap.fromTo(
    el,
    { height: h, paddingTop: pt, paddingBottom: pb, autoAlpha: 1 },
    {
      height: 0,
      paddingTop: 0,
      paddingBottom: 0,
      autoAlpha: 0,
      duration: 0.32,
      ease: "power2.inOut",
      onComplete: () => {
        gsap.set(el, { clearProps: "height, paddingTop, paddingBottom, overflow, willChange" });
        done();
      },
    }
  );
}

onMounted(() => {
  // 统一尊重系统「减少动态效果」偏好：命中时展开/收起直接落到终态，不做补间
  mm = gsap.matchMedia();
  mm.add("(prefers-reduced-motion: reduce)", () => {
    reduceMotion.value = true;
    return () => {
      reduceMotion.value = false;
    };
  });

  // 支持从仪表盘「签到失败 · 查看详情」等入口带筛选条件跳入（?accountId=&type=&status=）
  const q = route.query || {}
  if (/^\d+$/.test(String(q.accountId || ""))) store.selectedAccountId = Number(q.accountId);
  if (["all", "dorm", "activity"].includes(q.type)) store.typeFilter = q.type;
  if (["all", "success", "fail", "skip"].includes(q.status)) store.statusFilter = q.status;
  store.init();
});

onUnmounted(() => {
  mm?.revert();
});
</script>
