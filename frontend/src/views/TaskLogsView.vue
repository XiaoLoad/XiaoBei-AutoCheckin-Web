<template>
  <div class="flex flex-1 min-h-0 flex-col gap-6">
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
         min-h-[480px] 给列表卡片一个舒适下限（与 SignRecordsView 一致），短屏不至过矮、长屏仍随 flex-1 撑满 -->
    <div class="dash-card fade-up flex flex-1 min-h-[480px] flex-col rounded-2xl">
      <div class="flex-1 min-h-0 overflow-y-auto">
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
          class="flex items-stretch gap-3 px-3 py-3 transition hover:bg-cloud/40 sm:px-4"
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
          <button
            type="button"
            class="shrink-0 self-center rounded-lg p-1.5 text-ink-muted transition hover:bg-danger/[0.06] hover:text-danger"
            title="删除该条日志"
            @click="onDelete(row)"
          >
            <Icon name="trash" :size="14" />
          </button>
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
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { storeToRefs } from "pinia";
import { useTaskLogsStore } from "@/stores/taskLogs";
import { toast } from "@/utils/toast";
import Icon from "@/components/Icon.vue";
import BaseSelect from "@/components/BaseSelect.vue";
import StatCard from "@/components/StatCard.vue";
import BasePagination from "@/components/BasePagination.vue";

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

onMounted(() => {
  // 支持从仪表盘「签到失败 · 查看详情」等入口带筛选条件跳入（?accountId=&type=&status=）
  const q = route.query || {}
  if (/^\d+$/.test(String(q.accountId || ""))) store.selectedAccountId = Number(q.accountId);
  if (["all", "dorm", "activity"].includes(q.type)) store.typeFilter = q.type;
  if (["all", "success", "fail", "skip"].includes(q.status)) store.statusFilter = q.status;
  store.init();
});
</script>
