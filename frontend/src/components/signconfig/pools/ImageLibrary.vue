<template>
  <div class="flex min-h-0 gap-3">
    <!-- 左：分组侧栏（相册式管理 + 拖拽投放目标） -->
    <aside class="flex h-[72vh] w-52 shrink-0 flex-col overflow-hidden rounded-2xl dash-card">
      <div class="border-b border-ink/5 p-2">
        <div class="relative">
          <Icon name="search" :size="13" class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input
            v-model="groupQuery"
            type="text"
            placeholder="搜索分组…"
            class="w-full rounded-lg border border-ink/10 bg-cloud/40 py-1.5 pl-7 pr-2 text-xs text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/10"
          />
        </div>
      </div>
      <div class="xb-scroll flex-1 min-h-0 overflow-auto p-1.5">
        <!-- 全部（非投放目标） -->
        <div
          class="flex cursor-pointer items-center gap-1 rounded-lg px-2 py-1.5 text-sm transition"
          :class="groupFilter === 'all' ? 'bg-brand/10 font-medium text-brand' : 'text-ink-soft hover:bg-cloud'"
          @click="groupFilter = 'all'"
        >
          <span class="min-w-0 flex-1 truncate">全部</span>
          <span class="shrink-0 text-[11px] text-ink-muted">{{ counts.all }}</span>
        </div>
        <!-- 未分组（可投放） -->
        <div
          v-show="matchesGroupQuery('未分组')"
          class="flex cursor-pointer items-center gap-1 rounded-lg px-2 py-1.5 text-sm transition"
          :class="[
            groupFilter === 'ungrouped' ? 'bg-brand/10 font-medium text-brand' : 'text-ink-soft hover:bg-cloud',
            dropKey === 'ungrouped' ? 'ring-2 ring-brand' : ''
          ]"
          @click="groupFilter = 'ungrouped'"
          @dragover.prevent="onGroupDragOver('ungrouped', $event)"
          @dragleave="onGroupDragLeave('ungrouped')"
          @drop.prevent="onDropTo('ungrouped', $event)"
        >
          <span class="min-w-0 flex-1 truncate">未分组</span>
          <span class="shrink-0 text-[11px] text-ink-muted">{{ counts.ungrouped }}</span>
        </div>
        <!-- 用户自建分组（可投放；hover 显示重命名/删除） -->
        <div
          v-for="g in visibleGroups"
          :key="g.id"
          class="group/row flex cursor-pointer items-center gap-1 rounded-lg px-2 py-1.5 text-sm transition"
          :class="[
            groupFilter === g.id ? 'bg-brand/10 font-medium text-brand' : 'text-ink-soft hover:bg-cloud',
            dropKey === g.id ? 'ring-2 ring-brand' : ''
          ]"
          @click="editingGroupId === g.id ? null : (groupFilter = g.id)"
          @dragover.prevent="onGroupDragOver(g.id, $event)"
          @dragleave="onGroupDragLeave(g.id)"
          @drop.prevent="onDropTo(g.id, $event)"
        >
          <template v-if="editingGroupId === g.id">
            <input
              v-model="editingName"
              type="text"
              class="min-w-0 flex-1 rounded-lg border border-ink/10 bg-white px-2 py-1.5 text-xs text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/10"
              @keyup.enter="confirmRename"
              @click.stop
            />
            <button
              type="button"
              class="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-brand transition hover:bg-brand/10"
              aria-label="保存"
              @click.stop="confirmRename"
            >
              <Icon name="check" :size="14" />
            </button>
            <button
              type="button"
              class="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-ink-muted transition hover:bg-cloud"
              aria-label="取消"
              @click.stop="editingGroupId = null"
            >
              <Icon name="close" :size="14" />
            </button>
          </template>
          <template v-else>
            <span class="min-w-0 flex-1 truncate" :title="g.name">{{ g.name }}</span>
            <span class="shrink-0 text-[11px] text-ink-muted">{{ counts[g.id] ?? 0 }}</span>
            <span class="hidden shrink-0 items-center gap-0.5 group-hover/row:flex">
              <Icon name="edit" :size="12" class="cursor-pointer text-ink-muted hover:text-brand" @click.stop="startRename(g)" />
              <Icon name="trash" :size="12" class="cursor-pointer text-ink-muted hover:text-danger" @click.stop="removeGroup(g)" />
            </span>
          </template>
        </div>
        <!-- 新建分组 -->
        <div v-if="creating" class="space-y-1.5 rounded-lg bg-brand/5 p-2">
          <input
            v-model="newName"
            type="text"
            placeholder="分组名，如 3栋507"
            class="w-full rounded-lg border border-ink/10 bg-white px-2.5 py-2 text-xs text-ink outline-none transition placeholder:text-ink-muted focus:border-brand focus:ring-2 focus:ring-brand/10"
            @keyup.enter="confirmCreate"
            @keyup.esc="creating = false"
          />
          <div class="flex items-center gap-1.5">
            <button
              type="button"
              class="flex-1 rounded-lg bg-brand px-3 py-2 text-xs font-medium text-white transition hover:bg-brand-dark active:scale-[0.98]"
              @click="confirmCreate"
            >保存</button>
            <button
              type="button"
              class="flex-1 rounded-lg border border-ink/15 bg-white px-3 py-2 text-xs font-medium text-ink-soft transition hover:bg-cloud active:scale-[0.98]"
              @click="creating = false"
            >取消</button>
          </div>
        </div>
        <button
          v-else
          type="button"
          class="mt-0.5 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-ink/20 px-2 py-2 text-xs text-ink-soft transition hover:border-brand hover:text-brand"
          @click="creating = true"
        >
          <Icon name="plus" :size="13" />新建分组
        </button>
        <p v-if="groupsEmpty && groupQuery" class="px-2 py-1.5 text-center text-[11px] text-ink-muted">无匹配分组</p>
      </div>
      <p class="border-t border-ink/5 px-3 py-2 text-[11px] leading-relaxed text-ink-muted">
        同寝室账号共用同一分组；不同寝室各建各的组。
      </p>
    </aside>

    <!-- 右：图库网格 + 分页 -->
    <div
      class="relative flex h-[72vh] min-w-0 flex-1 flex-col gap-3"
      @dragenter.prevent="onFileDragEnter"
      @dragover.prevent="onFileDragOver"
      @dragleave="onFileDragLeave"
      @drop.prevent="onFileDrop"
    >
      <!-- 拖拽上传高亮层：仅外部文件拖入时显示 -->
      <div
        v-if="isFileDragOver"
        class="pointer-events-none absolute inset-0 z-20 flex items-center justify-center rounded-2xl border-2 border-dashed border-brand bg-brand/10 backdrop-blur-[1px]"
      >
        <div class="flex flex-col items-center gap-1.5 text-brand">
          <Icon name="image" :size="36" />
          <p class="text-sm font-medium">松开鼠标，上传到「{{ uploadTargetName }}」</p>
          <p class="text-[11px] text-brand/70">支持 JPG / PNG / WEBP，可批量拖入</p>
        </div>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="inline-flex rounded-xl bg-cloud p-1 text-sm">
          <button
            v-for="v in views"
            :key="v.value"
            type="button"
            class="rounded-lg px-3 py-1.5 font-medium transition"
            :class="view === v.value ? 'bg-white text-brand shadow-sm' : 'text-ink-muted hover:text-ink-soft'"
            @click="view = v.value"
          >
            {{ v.label }}
          </button>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-[11px] text-ink-muted">上传至：{{ uploadTargetName }}</span>
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-60"
            :disabled="uploading"
            @click="fileInput?.click()"
          >
            <span v-if="uploading" class="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
            <Icon v-else name="plus" :size="15" />{{ uploading ? '上传中…' : '上传图片' }}
          </button>
        </div>
      </div>

      <!-- 批量选择操作栏：有选中项时出现（GSAP 高度+透明度过渡，避免布局跳变） -->
      <Transition :css="false" @enter="onBarEnter" @leave="onBarLeave">
        <div v-if="selectedIds.size" class="overflow-hidden">
          <div class="flex flex-wrap items-center gap-2 rounded-xl border border-brand/20 bg-brand/5 px-3 py-2 text-sm">
        <label class="inline-flex cursor-pointer select-none items-center gap-1.5 text-ink-soft">
          <input
            type="checkbox"
            class="h-4 w-4 rounded border-ink/30 text-brand focus:ring-brand/20"
            :checked="allOnPageSelected"
            :indeterminate.prop="someOnPageSelected && !allOnPageSelected"
            @change="toggleSelectAllOnPage"
          />
          <span>已选 <span class="font-medium text-brand">{{ selectedIds.size }}</span> 张</span>
        </label>
        <div class="ml-auto flex flex-wrap items-center gap-1.5">
          <button type="button" class="rounded-lg border border-ink/15 bg-white px-2.5 py-1.5 text-xs text-ink-soft transition hover:bg-cloud" @click="selectAll">全选</button>
          <button type="button" class="rounded-lg border border-ink/15 bg-white px-2.5 py-1.5 text-xs text-ink-soft transition hover:bg-cloud" @click="invertSelect">反选</button>
          <button type="button" class="rounded-lg border border-ink/15 bg-white px-2.5 py-1.5 text-xs text-ink-soft transition hover:bg-cloud" @click="clearSelect">取消选择</button>
          <span class="mx-0.5 hidden h-4 w-px bg-ink/15 sm:inline-block" />
          <template v-if="view === 'trash'">
            <button
              type="button"
              class="inline-flex items-center gap-1 rounded-lg border border-ink/15 bg-white px-2.5 py-1.5 text-xs text-ink-soft transition hover:bg-cloud disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="batchRunning"
              @click="batchRestore"
            >
              <Icon name="refresh" :size="13" />恢复
            </button>
            <button
              type="button"
              class="inline-flex items-center gap-1 rounded-lg bg-danger px-2.5 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="batchRunning"
              @click="confirmBatchPurge"
            >
              <Icon name="trash" :size="13" />永久删除
            </button>
          </template>
          <template v-else>
            <button
              type="button"
              class="inline-flex items-center gap-1 rounded-lg border border-ink/15 bg-white px-2.5 py-1.5 text-xs text-ink-soft transition hover:bg-cloud disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="batchRunning"
              @click="openBatchMove"
            >
              <Icon name="layers" :size="13" />移动到分组
            </button>
            <button
              type="button"
              class="inline-flex items-center gap-1 rounded-lg border border-ink/15 bg-white px-2.5 py-1.5 text-xs text-ink-soft transition hover:bg-cloud disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="batchRunning"
              @click="confirmBatchTrash"
            >
              <Icon name="trash" :size="13" />移入回收站
            </button>
            <button
              v-if="view === 'active'"
              type="button"
              class="inline-flex items-center gap-1 rounded-lg border border-ink/15 bg-white px-2.5 py-1.5 text-xs text-ink-soft transition hover:bg-cloud disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="batchRunning"
              @click="batchMarkUsed"
            >
              <Icon name="check-circle" :size="13" />标记已用
            </button>
            <button
              v-if="view === 'used'"
              type="button"
              class="inline-flex items-center gap-1 rounded-lg border border-ink/15 bg-white px-2.5 py-1.5 text-xs text-ink-soft transition hover:bg-cloud disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="batchRunning"
              @click="batchRestore"
            >
              <Icon name="refresh" :size="13" />批量恢复
            </button>
          </template>
          </div>
          </div>
        </div>
      </Transition>

      <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" multiple class="hidden" @change="onFilePicked" />

      <p class="text-[11px] leading-relaxed text-ink-muted/80">
        上传自动压缩至 ≤180KB（B 平台提交口径）；也可将图片直接拖拽到此处批量上传；轮回使用的图片消费后进入「已使用」保留不删；图库中「删除」会移入回收站，回收站内「删除」才永久移除（保留 7 天后也会自动清除）；点击图片打开灯箱预览，可缩放、左右切换。
      </p>

      <div class="xb-scroll flex-1 min-h-0 overflow-y-auto overflow-x-hidden rounded-xl bg-cloud/40 px-1.5 py-1.5" :class="{ 'pb-28': uploadList.length }">
        <div v-if="pagedList.length === 0" class="flex h-full items-center justify-center text-sm text-ink-muted">
          {{ view === 'trash' ? '回收站为空' : view === 'used' ? '已使用列表为空' : '当前分组暂无图片' }}
        </div>
      <TransitionGroup
        v-else
        tag="div"
        name="xb-grid"
        :css="false"
        class="relative grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-5"
        @before-leave="onCardBeforeLeave"
        @enter="onCardEnter"
        @leave="onCardLeave"
      >
        <div
          v-for="img in pagedList"
          :key="img.id"
          class="group overflow-hidden rounded-xl border bg-white"
          :class="isSelected(img) ? 'border-brand ring-2 ring-brand/40' : 'border-ink/10'"
          :draggable="!img.inTrash"
          @dragstart="onDragStart(img, $event)"
          @dragend="onDragEnd"
        >
          <div class="relative aspect-[4/3] overflow-hidden bg-gradient-to-br from-cloud to-brand/10">
            <!-- 多选勾选框 -->
            <button
              type="button"
              class="absolute left-1.5 top-1.5 z-10 grid h-6 w-6 place-items-center rounded-md border transition"
              :class="isSelected(img) ? 'border-brand bg-brand text-white' : 'border-white/70 bg-white/80 text-transparent hover:bg-white'"
              :aria-pressed="isSelected(img)"
              :title="isSelected(img) ? '取消选择' : '选择'"
              @click.stop="onToggleSelect(img, $event)"
            >
              <Icon name="check" :size="14" />
            </button>
            <img
              v-if="urls[img.id]"
              :src="urls[img.id]"
              class="h-full w-full cursor-zoom-in object-contain transition duration-200 group-hover:scale-105"
              alt=""
              @click="openPreview(img)"
            />
            <Icon v-else name="image" :size="26" class="absolute inset-0 m-auto text-ink-muted" />
            <div
              v-if="urls[img.id]"
              class="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition group-hover:bg-black/30 group-hover:opacity-100"
            >
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-lg bg-white/90 px-2.5 py-1 text-xs text-ink shadow-sm hover:bg-white"
                @click.stop="openPreview(img)"
              >
                <Icon name="search" :size="13" />预览
              </button>
            </div>
            <span
              v-if="groupNameOf(img)"
              class="absolute bottom-1.5 left-1.5 rounded-md bg-black/45 px-1.5 py-0.5 text-[10px] text-white"
            >{{ groupNameOf(img) }}</span>
            <span v-if="!img.inTrash" class="absolute right-1.5 top-1.5 rounded-md bg-black/45 px-1.5 py-0.5 text-[10px] text-white opacity-0 transition group-hover:opacity-100">
              拖动到左侧分组可移动
            </span>
          </div>
          <div class="flex items-center justify-between gap-1 px-2 py-1.5">
            <p class="min-w-0 flex-1 truncate text-xs text-ink-soft" :title="img.name">{{ img.name }}</p>
            <span class="shrink-0 text-[11px] text-ink-muted">{{ img.sizeKb }}KB</span>
          </div>
          <div class="flex items-center justify-end gap-2 border-t border-ink/5 px-2 py-1.5">
            <template v-if="movingId === img.id">
              <BaseSelect v-model="moveTargetId" :options="moveOptions" :searchable="true" size="sm" class="min-w-0 flex-1" />
              <button class="shrink-0 text-[11px] text-brand hover:underline" @click="confirmMove">确定</button>
              <button class="shrink-0 text-[11px] text-ink-muted hover:underline" @click="movingId = null">取消</button>
            </template>
            <template v-else-if="view === 'used'">
              <button class="text-[11px] text-info hover:underline" @click="restore(img.id)">恢复至图库</button>
              <button class="text-[11px] text-ink-muted hover:text-brand" @click="startMove(img)">移动</button>
            </template>
            <template v-else-if="view === 'active'">
              <button class="text-[11px] text-ink-muted hover:text-brand" @click="startMove(img)">移动</button>
              <button class="text-[11px] text-ink-muted hover:text-brand" @click="markUsed(img.id)">标记已用</button>
              <button class="text-[11px] text-danger hover:underline" @click="toTrash(img.id)">删除</button>
            </template>
            <template v-else>
              <button class="text-[11px] text-info hover:underline" @click="restore(img.id)">恢复</button>
              <button class="text-[11px] text-danger hover:underline" @click="askDelete(img)">删除</button>
            </template>
          </div>
        </div>
      </TransitionGroup>
      </div>

      <div v-if="total > 0" class="mt-auto flex justify-center border-t border-ink/5 pt-3">
        <BasePagination :page="page" :page-size="pageSize" :total="total" :page-size-options="[12, 24, 48, 96]" @update:page="page = $event" @update:pageSize="onPageSizeChange" />
      </div>

      <!-- 上传进度与结果浮层：锚定在右侧卡片内（absolute），始终贴右下角可见，不被图片滚动推走 -->
      <transition name="fade">
        <div
          v-if="uploadList.length"
          class="absolute bottom-3 right-3 z-30 w-80 max-w-[calc(100%-1.5rem)] overflow-hidden rounded-2xl dash-card shadow-xl"
        >
          <div class="flex items-center justify-between gap-2 border-b border-ink/5 px-3 py-2">
            <span class="text-xs font-medium text-ink-soft">
              {{ isUploading ? '上传中…' : `完成（成功 ${doneCount} · 失败 ${errorCount}）` }}
            </span>
            <button
              type="button"
              class="grid h-5 w-5 place-items-center rounded text-ink-muted transition hover:bg-cloud hover:text-ink"
              aria-label="关闭"
              @click="closeUploadPanel"
            >
              <Icon name="close" :size="12" />
            </button>
          </div>
          <div class="xb-scroll max-h-64 space-y-1.5 overflow-auto p-2">
            <div
              v-for="(it, idx) in uploadList"
              :key="idx"
              class="rounded-lg bg-cloud/50 px-2 py-1.5"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="min-w-0 flex-1 truncate text-[11px] text-ink-soft" :title="it.name">{{ it.name }}</span>
                <span class="shrink-0 text-[10px] font-medium" :class="statusColor(it.status)">{{ statusLabel(it) }}</span>
              </div>
              <div v-if="it.status === 'uploading' || it.status === 'queued'" class="mt-1 h-1 w-full overflow-hidden rounded-full bg-ink/10">
                <div class="h-full rounded-full bg-brand transition-all duration-200" :style="{ width: it.progress + '%' }" />
              </div>
              <p v-if="it.status === 'error'" class="mt-0.5 truncate text-[10px] text-danger" :title="it.error">{{ it.error }}</p>
            </div>
          </div>
        </div>
      </transition>

      <!-- 批量操作进度与结果浮层：锚定在右侧卡片内右下角（与上传面板同角，二者互斥） -->
      <transition name="fade">
        <div
          v-if="batchPanel.show"
          class="absolute bottom-3 right-3 z-30 w-80 max-w-[calc(100%-1.5rem)] overflow-hidden rounded-2xl dash-card shadow-xl"
        >
          <div class="flex items-center justify-between gap-2 border-b border-ink/5 px-3 py-2">
            <span class="text-xs font-medium text-ink-soft">{{ batchPanel.title }}</span>
            <button
              type="button"
              class="grid h-5 w-5 place-items-center rounded text-ink-muted transition hover:bg-cloud hover:text-ink"
              aria-label="关闭"
              @click="batchPanel.show = false"
            >
              <Icon name="close" :size="12" />
            </button>
          </div>
          <div class="px-3 py-2">
            <div class="h-1.5 w-full overflow-hidden rounded-full bg-ink/10">
              <div class="h-full rounded-full bg-brand transition-all duration-200" :style="{ width: (batchPanel.total ? (batchPanel.done / batchPanel.total * 100) : 0) + '%' }" />
            </div>
            <p class="mt-1.5 text-[11px] text-ink-muted">{{ batchPanel.done }} / {{ batchPanel.total }}</p>
            <div v-if="batchPanel.failed.length" class="xb-scroll mt-2 max-h-32 space-y-1 overflow-auto">
              <p class="text-[11px] font-medium text-danger">以下 {{ batchPanel.failed.length }} 张失败：</p>
              <p v-for="f in batchPanel.failed" :key="f.id" class="truncate text-[10px] text-ink-muted" :title="f.error">#{{ f.id }}：{{ f.error }}</p>
            </div>
          </div>
        </div>
      </transition>

      <!-- 批量移入回收站后的撤销条：底部居中，8 秒后自动消失 -->
      <transition name="fade">
        <div
          v-if="undoState.visible"
          class="absolute bottom-3 left-1/2 z-40 flex -translate-x-1/2 items-center gap-3 rounded-2xl dash-card px-4 py-2.5 text-sm shadow-xl"
        >
          <Icon name="trash" :size="15" class="text-ink-muted" />
          <span class="text-ink-soft">已移入回收站 {{ undoState.ids.length }} 张</span>
          <button type="button" class="font-medium text-brand hover:underline" @click="undoBatchTrash">撤销</button>
          <button
            type="button"
            class="grid h-5 w-5 place-items-center rounded text-ink-muted transition hover:bg-cloud hover:text-ink"
            aria-label="关闭"
            @click="undoState.visible = false"
          >
            <Icon name="close" :size="12" />
          </button>
        </div>
      </transition>
    </div>

    <!-- 回收站删除二次确认 -->
    <ConfirmModal
      v-model="showDelConfirm"
      title="确认删除图片"
      :message="pendingDelete ? `「${pendingDelete.name}」删除后将从磁盘永久移除且不可恢复，确定要删除吗？` : ''"
      icon="trash"
      danger
      confirm-text="删除"
      :confirming="deleting"
      @confirm="confirmDelete"
    />

    <!-- 批量移动到分组 -->
    <ConfirmModal
      v-model="showBatchMove"
      title="移动到分组"
      icon="layers"
      confirm-text="移动"
      :confirming="batchMoving"
      :close-on-overlay="!batchMoving"
      :close-on-esc="!batchMoving"
      @confirm="confirmBatchMove"
    >
      <div class="space-y-2">
        <p class="text-xs text-ink-muted">将选中的 {{ selectedIds.size }} 张图片移动到：</p>
        <BaseSelect v-model="batchMoveTarget" :options="moveOptions" :searchable="true" size="sm" placeholder="选择目标分组" />
        <div v-if="creatingGroup" class="flex items-center gap-1.5">
          <input
            v-model="newGroupName"
            type="text"
            placeholder="新分组名"
            class="min-w-0 flex-1 rounded-lg border border-ink/10 bg-white px-2.5 py-2 text-xs text-ink outline-none transition placeholder:text-ink-muted focus:border-brand focus:ring-2 focus:ring-brand/10"
            @keyup.enter="createAndSelectGroup"
          />
          <button type="button" class="rounded-lg bg-brand px-3 py-2 text-xs font-medium text-white transition hover:bg-brand-dark" @click="createAndSelectGroup">确定</button>
          <button type="button" class="rounded-lg border border-ink/15 bg-white px-3 py-2 text-xs text-ink-soft transition hover:bg-cloud" @click="creatingGroup = false; newGroupName = ''">取消</button>
        </div>
        <button v-else type="button" class="text-xs text-brand hover:underline" @click="creatingGroup = true">+ 新建分组</button>
      </div>
    </ConfirmModal>

    <!-- 批量移入回收站（二次确认） -->
    <ConfirmModal
      v-model="showBatchTrash"
      title="移入回收站"
      icon="trash"
      danger
      confirm-text="移入回收站"
      :confirming="batchRunning"
      :close-on-overlay="!batchRunning"
      :close-on-esc="!batchRunning"
      @confirm="confirmBatchTrashOk"
    >
      <p>确认将选中的 <span class="font-medium text-ink">{{ selectedIds.size }}</span> 张图片移入回收站吗？移入后仍可在「回收站」恢复，本次操作完成后也提供撤销。</p>
    </ConfirmModal>

    <!-- 回收站批量永久删除（高风险确认，明确不可恢复） -->
    <ConfirmModal
      v-model="showBatchPurge"
      title="永久删除"
      icon="alert"
      danger
      confirm-text="永久删除"
      :confirming="batchRunning"
      :close-on-overlay="!batchRunning"
      :close-on-esc="!batchRunning"
      @confirm="confirmBatchPurgeOk"
    >
      <p class="font-medium text-danger">此操作不可恢复！</p>
      <p class="mt-1">确认永久删除选中的 <span class="font-medium text-ink">{{ selectedIds.size }}</span> 张图片吗？删除后将从磁盘移除且无法找回。</p>
    </ConfirmModal>
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch, onBeforeUnmount } from 'vue'
import PhotoSwipeLightbox from 'photoswipe/lightbox'
import PhotoSwipe from 'photoswipe'
import Icon from '@/components/Icon.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import BasePagination from '@/components/BasePagination.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { fetchImageBlobUrl } from '@/api/signConfig'
import toast from '@/utils/toast'
import gsap from 'gsap'

const store = useSignConfigStore()
const view = ref('active')
const views = [
  { value: 'active', label: '图库' },
  { value: 'used', label: '已使用' },
  { value: 'trash', label: '回收站' }
]

// ── 批量选择：selectedIds 为当前选中图片 id 集合（跨分页保持）；lastAnchorId 用于 Shift 连续选 ──
const selectedIds = ref(new Set())
const lastAnchorId = ref(null)
const isSelected = (img) => selectedIds.value.has(img.id)
const allOnPageSelected = computed(() =>
  pagedList.value.length > 0 && pagedList.value.every((i) => selectedIds.value.has(i.id))
)
const someOnPageSelected = computed(() => pagedList.value.some((i) => selectedIds.value.has(i.id)))
function toggleOne(id) {
  const s = selectedIds.value
  if (s.has(id)) s.delete(id)
  else s.add(id)
}
function onToggleSelect(img, e) {
  if (e && e.shiftKey && lastAnchorId.value != null) {
    const ids = pagedList.value.map((i) => i.id)
    const a = ids.indexOf(lastAnchorId.value)
    const b = ids.indexOf(img.id)
    if (a !== -1 && b !== -1) {
      const [lo, hi] = a < b ? [a, b] : [b, a]
      for (let k = lo; k <= hi; k++) selectedIds.value.add(ids[k])
      return
    }
  }
  // 普通点击 / Ctrl 跳选 / Shift 锚点失效：切换当前项并设为新锚点
  toggleOne(img.id)
  lastAnchorId.value = img.id
}
function toggleSelectAllOnPage() {
  const s = selectedIds.value
  if (allOnPageSelected.value) pagedList.value.forEach((i) => s.delete(i.id))
  else pagedList.value.forEach((i) => s.add(i.id))
}
function selectAll() {
  const s = selectedIds.value
  list.value.forEach((i) => s.add(i.id))
}
function invertSelect() {
  const s = selectedIds.value
  list.value.forEach((i) => (s.has(i.id) ? s.delete(i.id) : s.add(i.id)))
}
function clearSelect() {
  selectedIds.value.clear()
  lastAnchorId.value = null
}

// ── 批量操作：进度面板 + 部分失败汇总；无批量接口，循环单图端点逐张 try/catch ──
const batchRunning = ref(false)
const batchPanel = ref({ show: false, title: '', done: 0, total: 0, failed: [] })
async function runBatch(ids, fn) {
  const total = ids.length
  batchPanel.value = { show: true, title: '处理中…', done: 0, total, failed: [] }
  batchRunning.value = true
  const successIds = []
  const failed = []
  try {
    for (let i = 0; i < total; i++) {
      const id = ids[i]
      try {
        await fn(id)
        successIds.push(id)
      } catch (err) {
        failed.push({ id, error: (err && err.message) || '操作失败' })
      }
      batchPanel.value.done = i + 1
    }
    batchPanel.value.title = failed.length
      ? `完成（成功 ${successIds.length} · 失败 ${failed.length}）`
      : `已完成 ${successIds.length} 张`
  } finally {
    batchRunning.value = false
  }
  if (!failed.length) {
    setTimeout(() => {
      if (!batchPanel.value.failed.length && batchPanel.value.total === total) batchPanel.value.show = false
    }, 1500)
  }
  return { successIds, failed }
}

// 批量移动到分组（含就地新建分组）
const showBatchMove = ref(false)
const batchMoveTarget = ref('')
const creatingGroup = ref(false)
const newGroupName = ref('')
const batchMoving = ref(false)
function openBatchMove() {
  if (!selectedIds.value.size) return
  batchMoveTarget.value = ''
  creatingGroup.value = false
  newGroupName.value = ''
  showBatchMove.value = true
}
async function createAndSelectGroup() {
  const name = newGroupName.value.trim()
  if (!name) {
    toast('请填写分组名称', 'error')
    return
  }
  const groups = await store.createImageGroup(name)
  const last = groups[groups.length - 1]
  if (last) batchMoveTarget.value = String(last.id)
  creatingGroup.value = false
  newGroupName.value = ''
}
async function confirmBatchMove() {
  const target = batchMoveTarget.value === '' ? null : Number(batchMoveTarget.value)
  const ids = [...selectedIds.value]
  batchMoving.value = true
  try {
    const { successIds, failed } = await runBatch(ids, (id) => store.moveImage(id, target, { silent: true }))
    showBatchMove.value = false
    clearSelect()
    const gname = target == null ? '未分组' : (store.imageGroups.find((g) => g.id === target)?.name || '分组')
    if (failed.length) toast(`已移动 ${successIds.length} 张，${failed.length} 张失败`, 'error')
    else toast(`已移动 ${successIds.length} 张到「${gname}」`, 'success')
  } finally {
    batchMoving.value = false
  }
}

// 批量移入回收站（二次确认 + 完成后撤销条）
const showBatchTrash = ref(false)
const undoState = ref({ visible: false, ids: [], timer: null })
function confirmBatchTrash() {
  if (!selectedIds.value.size) return
  showBatchTrash.value = true
}
async function confirmBatchTrashOk() {
  const ids = [...selectedIds.value]
  showBatchTrash.value = false
  const { successIds, failed } = await runBatch(ids, (id) => store.trashImage(id, { silent: true }))
  clearSelect()
  if (successIds.length) {
    undoState.value.ids = successIds
    undoState.value.visible = true
    if (undoState.value.timer) clearTimeout(undoState.value.timer)
    undoState.value.timer = setTimeout(() => { undoState.value.visible = false }, 8000)
  }
  if (failed.length) toast(`已移入回收站 ${successIds.length} 张，${failed.length} 张失败`, 'error')
  else if (successIds.length) toast(`已移入回收站 ${successIds.length} 张`, 'success')
}
async function undoBatchTrash() {
  const ids = undoState.value.ids
  undoState.value.visible = false
  if (undoState.value.timer) clearTimeout(undoState.value.timer)
  if (!ids.length) return
  const { failed } = await runBatch(ids, (id) => store.restoreImage(id, { silent: true }))
  if (failed.length) toast(`撤销失败 ${failed.length} 张`, 'error')
  else toast(`已撤销，恢复 ${ids.length} 张至图库`, 'success')
}

// 回收站批量永久删除（高风险确认）
const showBatchPurge = ref(false)
function confirmBatchPurge() {
  if (!selectedIds.value.size) return
  showBatchPurge.value = true
}
async function confirmBatchPurgeOk() {
  const ids = [...selectedIds.value]
  showBatchPurge.value = false
  const { successIds, failed } = await runBatch(ids, (id) => store.deleteImage(id, { silent: true }))
  clearSelect()
  if (failed.length) toast(`已删除 ${successIds.length} 张，${failed.length} 张失败`, 'error')
  else toast(`已永久删除 ${successIds.length} 张`, 'success')
}

// 批量标记已使用（active 视图；可逆，无需确认）
async function batchMarkUsed() {
  if (!selectedIds.value.size) return
  const ids = [...selectedIds.value]
  const { successIds, failed } = await runBatch(ids, (id) => store.markUsed(id, { silent: true }))
  clearSelect()
  if (failed.length) toast(`已标记 ${successIds.length} 张，${failed.length} 张失败`, 'error')
  else toast(`已标记 ${successIds.length} 张为已使用`, 'success')
}

// 批量恢复（已使用/回收站视图）：恢复至图库；列表、分组计数与空状态随 store 刷新自动同步
async function batchRestore() {
  if (!selectedIds.value.size) return
  const ids = [...selectedIds.value]
  const { successIds, failed } = await runBatch(ids, (id) => store.restoreImage(id, { silent: true }))
  clearSelect()
  if (failed.length) toast(`已恢复 ${successIds.length} 张，${failed.length} 张失败`, 'error')
  else toast(`已恢复 ${successIds.length} 张至图库`, 'success')
}

// ── GSAP 过渡：批量操作栏显隐（高度+透明度，消除布局跳变）──
function onBarEnter(el, done) {
  gsap.killTweensOf(el)
  gsap.fromTo(el, { height: 0, opacity: 0 }, {
    height: el.scrollHeight, opacity: 1, duration: 0.25, ease: 'power2.out',
    onComplete: () => { el.style.height = ''; el.style.opacity = ''; done() }
  })
}
function onBarLeave(el, done) {
  gsap.killTweensOf(el)
  gsap.to(el, { height: 0, opacity: 0, duration: 0.18, ease: 'power2.in', onComplete: done })
}

// ── GSAP 过渡：网格卡片进入/离开；重排补位由 .xb-grid-move 的 FLIP 过渡完成 ──
function onCardEnter(el, done) {
  gsap.killTweensOf(el)
  gsap.fromTo(el, { opacity: 0, y: 10, scale: 0.97 }, {
    opacity: 1, y: 0, scale: 1, duration: 0.28, ease: 'power2.out',
    clearProps: 'transform,opacity', onComplete: done
  })
}
function onCardBeforeLeave(el) {
  // 离场卡片钉在原位并脱离文档流，其余卡片经 FLIP 平滑补位（grid 容器须为 relative）
  const { offsetLeft, offsetTop, offsetWidth, offsetHeight } = el
  Object.assign(el.style, {
    position: 'absolute', left: `${offsetLeft}px`, top: `${offsetTop}px`,
    width: `${offsetWidth}px`, height: `${offsetHeight}px`, margin: '0'
  })
}
function onCardLeave(el, done) {
  gsap.killTweensOf(el)
  gsap.to(el, { opacity: 0, scale: 0.96, duration: 0.2, ease: 'power2.in', onComplete: done })
}

// ── 分组（左栏）：groupFilter 为 'all' | 'ungrouped' | 分组 id（数字）；
// 分组名由用户自建（如寝室号"3栋507"），同寝室账号共用同一分组 ──
const groupFilter = ref('all')
// 切换视图/分组时清空批量选择，避免跨视图误操作（须在 groupFilter 声明后注册，避免 TDZ）
watch([view, groupFilter], () => { clearSelect() })
const groupQuery = ref('')
const creating = ref(false)
const newName = ref('')
const editingGroupId = ref(null)
const editingName = ref('')

// 分组搜索：按名称包含匹配（大小写不敏感），命中行为空时视为全显
const groupQueryHit = (name) => {
  const q = groupQuery.value.trim().toLowerCase()
  return !q || String(name).toLowerCase().includes(q)
}
const matchesGroupQuery = groupQueryHit
const visibleGroups = computed(() => store.imageGroups.filter((g) => groupQueryHit(g.name)))
const groupsEmpty = computed(() => visibleGroups.value.length === 0)

// 当前视图下的图片池（视图感知：图库=active，已使用=used，回收站=trash）
const viewPool = computed(() => {
  const v = view.value
  return store.imageLibrary.filter((i) => {
    if (v === 'trash') return i.inTrash
    if (v === 'used') return i.used
    return !i.inTrash && !i.used
  })
})
const counts = computed(() => {
  const byGroup = { all: viewPool.value.length, ungrouped: 0 }
  for (const g of store.imageGroups) byGroup[g.id] = 0
  for (const i of viewPool.value) {
    if (i.groupId == null) byGroup.ungrouped += 1
    else if (byGroup[i.groupId] != null) byGroup[i.groupId] += 1
  }
  return byGroup
})
// 图片角标的所属分组名
const groupNameOf = (img) => {
  const g = store.imageGroups.find((x) => x.id === img.groupId)
  return g ? g.name : ''
}

const list = computed(() => {
  const pool = viewPool.value
  if (groupFilter.value === 'all') return pool
  if (groupFilter.value === 'ungrouped') return pool.filter((i) => i.groupId == null)
  return pool.filter((i) => i.groupId === groupFilter.value)
})

// 选中项离开当前列表（移动/删除/恢复等数据变化）时同步清理：立即从选中集合移除并更新计数；
// 全部失效时自动退出批量选择，避免出现无法操作的空选中态
watch(
  () => list.value.map((i) => i.id).join('|'),
  () => {
    if (!selectedIds.value.size) return
    const present = new Set(list.value.map((i) => i.id))
    let removed = false
    for (const id of [...selectedIds.value]) {
      if (!present.has(id)) {
        selectedIds.value.delete(id)
        removed = true
      }
    }
    if (removed && selectedIds.value.size === 0) clearSelect()
  }
)

// 新建/重命名分组
async function confirmCreate() {
  const name = newName.value.trim()
  if (!name) {
    toast('请填写分组名称', 'error')
    return
  }
  const groups = await store.createImageGroup(name)
  const last = groups[groups.length - 1]
  if (last) groupFilter.value = last.id
  creating.value = false
  newName.value = ''
  toast('分组已创建', 'success')
}
function startRename(g) {
  editingGroupId.value = g.id
  editingName.value = g.name
}
async function confirmRename() {
  const name = editingName.value.trim()
  if (!name) {
    toast('请填写分组名称', 'error')
    return
  }
  await store.renameImageGroup(editingGroupId.value, name)
  editingGroupId.value = null
  toast('分组已重命名', 'success')
}
async function removeGroup(g) {
  // 图片回落未分组（不随组删除），无数据损失
  await store.deleteImageGroup(g.id)
  if (groupFilter.value === g.id) groupFilter.value = 'all'
  toast('分组已删除，组内图片移至未分组', 'success')
}

// ── 上传：目标为当前分组（全部/未分组视图下归未分组）──
const fileInput = ref(null)
const uploading = ref(false)
const uploadTargetName = computed(() => {
  if (typeof groupFilter.value === 'number') {
    const g = store.imageGroups.find((x) => x.id === groupFilter.value)
    return g ? g.name : '未分组'
  }
  return '未分组'
})
const uploadGroupId = computed(() => (typeof groupFilter.value === 'number' ? groupFilter.value : null))

// 允许的图片类型（后端归一化为 JPEG；前端先按常见格式预校验，不支持 GIF）
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const MAX_SIZE = 5 * 1024 * 1024
function validateImage(f) {
  const okType = ALLOWED_TYPES.includes(f.type) || /\.(jpe?g|png|webp)$/i.test(f.name)
  if (!okType) {
    toast(`「${f.name}」格式不支持，仅支持 JPG / PNG / WEBP`, 'error')
    return false
  }
  if (f.size > MAX_SIZE) {
    toast(`「${f.name}」超过 5MB 上限`, 'error')
    return false
  }
  return true
}

// 上传队列：逐张展示进度与结果（queued/uploading/done/error）
const uploadList = ref([])
const showUploadPanel = ref(false)
const isUploading = computed(() =>
  uploadList.value.some((i) => i.status === 'uploading' || i.status === 'queued')
)
const doneCount = computed(() => uploadList.value.filter((i) => i.status === 'done').length)
const errorCount = computed(() => uploadList.value.filter((i) => i.status === 'error').length)
function statusLabel(it) {
  if (it.status === 'queued') return '等待中'
  if (it.status === 'uploading') return `${it.progress}%`
  if (it.status === 'done') return '成功'
  return '失败'
}
function statusColor(status) {
  return {
    queued: 'text-ink-muted',
    uploading: 'text-brand',
    done: 'text-success',
    error: 'text-danger'
  }[status] || 'text-ink-muted'
}
function closeUploadPanel() {
  uploadList.value = []
  showUploadPanel.value = false
}

// 统一入口：校验 → 顺序逐张上传（后端单文件接口）→ 实时进度与结果
async function handleFiles(fileList) {
  const files = Array.from(fileList || []).filter((f) => validateImage(f))
  if (!files.length) return
  uploading.value = true
  showUploadPanel.value = true
  uploadList.value = files.map((f) => ({ name: f.name, status: 'queued', progress: 0, error: '' }))
  let okCount = 0
  try {
    for (let i = 0; i < files.length; i++) {
      const it = uploadList.value[i]
      it.status = 'uploading'
      try {
        await store.uploadImage(files[i], uploadGroupId.value, (p) => { it.progress = p }, { silent: true })
        it.status = 'done'
        it.progress = 100
        okCount += 1
      } catch (err) {
        it.status = 'error'
        it.error = err.message || '上传失败'
      }
    }
    if (okCount) toast(`已上传 ${okCount} 张图片至「${uploadTargetName.value}」`, 'success')
  } finally {
    uploading.value = false
  }
}

// 点击选择文件：复用统一入口（兼容原上传方式）
function onFilePicked(e) {
  const files = e.target.files
  e.target.value = ''
  handleFiles(files)
}

// ── 拖拽上传（区分外部文件拖拽与内部卡片移动）──
const isFileDragOver = ref(false)
let dragDepth = 0
function hasFiles(e) {
  const t = e.dataTransfer && e.dataTransfer.types
  return !!t && Array.from(t).includes('Files')
}
function onFileDragEnter(e) {
  if (!hasFiles(e)) return
  dragDepth += 1
  isFileDragOver.value = true
}
function onFileDragOver(e) {
  if (!hasFiles(e)) return
  e.preventDefault() // 必须阻止默认行为，否则 drop 不触发
}
function onFileDragLeave(e) {
  if (!hasFiles(e)) return
  dragDepth = Math.max(0, dragDepth - 1)
  if (dragDepth === 0) isFileDragOver.value = false
}
function onFileDrop(e) {
  if (!hasFiles(e)) return // 内部卡片拖拽走分组移动逻辑，不在此处理
  e.preventDefault()
  dragDepth = 0
  isFileDragOver.value = false
  handleFiles(e.dataTransfer.files)
}

// ── 拖拽移动（C1 原生 HTML5）：拖卡片 → 放到左栏分组行 ──
const draggingId = ref(null)
const dropKey = ref(null)
function onDragStart(img, e) {
  draggingId.value = img.id
  e.dataTransfer.setData('text/plain', String(img.id)) // Firefox 需要数据才允许拖放
  e.dataTransfer.effectAllowed = 'move'
}
function onDragEnd() {
  draggingId.value = null
  dropKey.value = null
}
// 分组行的拖拽高亮/投放：仅内部卡片拖拽（非外部文件）才响应，避免文件拖过时被误高亮
function onGroupDragOver(key, e) {
  if (hasFiles(e)) return
  dropKey.value = key
}
function onGroupDragLeave(key) {
  if (dropKey.value === key) dropKey.value = null
}
async function onDropTo(key, e) {
  if (e && hasFiles(e)) return // 文件拖放走上传逻辑，不在此处理
  const img = store.imageLibrary.find((i) => i.id === draggingId.value)
  const target = key === 'ungrouped' ? null : key
  draggingId.value = null
  dropKey.value = null
  if (!img || img.groupId === target) return
  await store.moveImage(img.id, target)
  toast('已移动到目标分组', 'success')
}

// ── 移动（兜底）：可搜索下拉，BaseSelect 面板 Teleport 到 body 不会被卡片裁切 ──
const movingId = ref(null)
const moveTargetId = ref('')
const moveOptions = computed(() => [
  { label: '未分组', value: '' },
  ...store.imageGroups.map((g) => ({ label: g.name, value: String(g.id) }))
])
function startMove(img) {
  movingId.value = img.id
  moveTargetId.value = img.groupId == null ? '' : String(img.groupId)
}
async function confirmMove() {
  const target = moveTargetId.value === '' ? null : Number(moveTargetId.value)
  await store.moveImage(movingId.value, target)
  movingId.value = null
  toast('已移动到目标分组', 'success')
}

// ── 缩略图：blob objectURL 会话级缓存 ──
const urls = reactive({})

// ── 图片原始尺寸缓存 ──
// PhotoSwipe v5 必须显式给出 width/height：缺失时它无从判断原始比例，会退回按视口铺满，
// 图片因此被拉伸变形；缩放级别也由该尺寸推算，缺失会导致滚轮缩放失效。
// 尺寸取自 blob 自身的 naturalWidth/Height，与灯箱实际展示的图同源，不受缩略图缩放影响。
const sizeCache = reactive({})
function probeSize(src) {
  if (!sizeCache[src]) {
    sizeCache[src] = new Promise((resolve) => {
      const im = new Image()
      im.onload = () => resolve({ width: im.naturalWidth || 0, height: im.naturalHeight || 0 })
      im.onerror = () => resolve({ width: 0, height: 0 })
      im.src = src
    })
  }
  return sizeCache[src]
}

// ── 分页：前端分页（图库上限 50 张），翻页后预览范围与所见一致 ──
const page = ref(1)
const pageSize = ref(24)
const total = computed(() => list.value.length)
const pagedList = computed(() => list.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
watch([groupFilter, view, () => store.imageLibrary.length], () => { page.value = 1 })
// 当前页图片被移走/删除导致页码越界时回退到第一页
watch(total, (t) => {
  if (page.value > Math.max(1, Math.ceil(t / pageSize.value))) page.value = 1
})
function onPageSizeChange(size) {
  pageSize.value = size
  page.value = 1
}

// 缩略图预取：只拉当前页，翻页时增量加载
watch(pagedList, async (rows) => {
  // 清理已删除图片的镜像条目（物理删除时 blobCache 已 revoke，这里仅丢弃组件级引用）
  const alive = new Set(store.imageLibrary.map((i) => i.id))
  for (const k of Object.keys(urls)) {
    if (!alive.has(Number(k)) && !alive.has(k)) delete urls[k]
  }
  for (const r of rows) {
    if (!urls[r.id]) {
      try { urls[r.id] = await fetchImageBlobUrl(r.id) } catch { /* 文件丢失时留图标占位 */ }
    }
    // 预热尺寸，打开灯箱时命中缓存无需等待
    if (urls[r.id]) probeSize(urls[r.id])
  }
}, { immediate: true })

// ── 全屏灯箱（PhotoSwipeLightbox）：带默认 UI（关闭/缩放按钮、左右箭头、计数器）；
// 灯箱范围 = 当前页全部图片，打开前确保缩略图 url 已就绪 ──
let lightbox = null
async function openPreview(img) {
  await Promise.all(pagedList.value.map(async (r) => {
    if (!urls[r.id]) {
      try { urls[r.id] = await fetchImageBlobUrl(r.id) } catch { /* 占位图标 */ }
    }
  }))
  const rows = pagedList.value.filter((r) => urls[r.id])
  const sizes = await Promise.all(rows.map((r) => probeSize(urls[r.id])))
  // 带 width/height 后 PhotoSwipe 按原始宽高比居中适配，不再铺满拉伸；缩放级别亦由此推算
  const dataSource = rows.map((r, i) => {
    const { width, height } = sizes[i]
    return width && height ? { src: urls[r.id], width, height } : { src: urls[r.id] }
  })
  const index = dataSource.findIndex((d) => d.src === urls[img.id])
  if (!dataSource.length || index === -1) return
  // 每次打开都新建实例，先销毁旧的，避免残留 DOM 与事件监听
  lightbox?.destroy()
  lightbox = new PhotoSwipeLightbox({
    dataSource,
    index,
    showHideAnimationType: 'fade',
    wheelToZoom: true,
    pswpModule: PhotoSwipe
  })
  lightbox.init()
  lightbox.loadAndOpen(index)
}
onBeforeUnmount(() => {
  lightbox?.destroy()
  if (undoState.value.timer) clearTimeout(undoState.value.timer)
})

function toTrash(id) { store.trashImage(id) }
function restore(id) { store.restoreImage(id) }
function remove(id) { store.deleteImage(id) }
function markUsed(id) { store.markUsed(id) }

// 回收站删除二次确认：确认后物理删除（不可恢复）
const pendingDelete = ref(null)
const showDelConfirm = ref(false)
const deleting = ref(false)
function askDelete(img) {
  pendingDelete.value = img
  showDelConfirm.value = true
}
async function confirmDelete() {
  if (!pendingDelete.value) return
  deleting.value = true
  try {
    await remove(pendingDelete.value.id)
    showDelConfirm.value = false
    pendingDelete.value = null
  } finally {
    deleting.value = false
  }
}
</script>

<style scoped>
/* TransitionGroup FLIP：网格重排（卡片移动/删除/恢复/翻页）时位移平滑过渡；
   离场卡片的绝对定位让位由 onCardBeforeLeave 钩子负责，进入/离开透明度由 GSAP 驱动 */
.xb-grid-move {
  transition: transform 0.28s cubic-bezier(0.22, 0.61, 0.36, 1);
}
</style>
