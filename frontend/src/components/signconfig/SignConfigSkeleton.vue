<template>
  <!-- 资源类 Tab（系统资源 / 我的资源）：sub-tab 条 + 资源卡网格 -->
  <div v-if="tab === 'resources'" class="space-y-4">
    <div class="inline-flex rounded-xl bg-cloud p-1">
      <div v-for="i in subTabCount" :key="i" class="sk h-8 w-20 rounded-lg" />
    </div>
    <div class="dash-card p-4">
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <div v-for="i in 6" :key="i" class="sk h-20 rounded-xl" />
      </div>
    </div>
  </div>

  <!-- 配置套 / 账号任务：左列表 + 右编辑器（与真实 Tab 同结构、同 flex 槽位） -->
  <div v-else class="flex flex-1 min-h-0 gap-4">
    <aside class="flex w-56 shrink-0 flex-col overflow-hidden rounded-2xl dash-card xl:w-60">
      <div class="flex shrink-0 items-center justify-between border-b border-ink/5 p-3">
        <div class="sk h-4 w-20 rounded" />
        <div class="sk h-7 w-14 rounded-lg" />
      </div>
      <div class="xb-scroll flex-1 min-h-0 overflow-auto p-2">
        <div v-for="i in 6" :key="i" class="sk mb-2 h-8 rounded-lg" />
      </div>
    </aside>

    <div class="xb-scroll flex-1 min-h-0 overflow-auto">
      <div class="mb-3 flex items-center justify-between gap-2">
        <div class="sk h-5 w-44 rounded" />
        <div class="flex gap-2">
          <div class="sk h-9 w-24 rounded-lg" />
          <div class="sk h-9 w-24 rounded-lg" />
        </div>
      </div>

      <div class="mb-4 rounded-xl border-l-4 border-ink/10 bg-cloud/40 px-4 py-3">
        <div class="sk h-3 w-full rounded" />
        <div class="sk mt-2 h-3 w-3/4 rounded" />
      </div>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <div v-for="i in 6" :key="i" class="dash-card p-4">
          <div class="sk mb-3 h-4 w-24 rounded" />
          <div class="space-y-2">
            <div class="sk h-3 w-full rounded" />
            <div class="sk h-3 w-2/3 rounded" />
            <div class="sk h-8 w-full rounded-lg" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 加载态骨架屏：按当前 Tab 渲染与真实内容同结构、同 flex 槽位的占位，
// 使加载完成时从骨架切到真实内容的视觉跳动降到最低（DOM 结构与高度一致）。
defineProps({
  tab: { type: String, default: 'default' },
  subTabCount: { type: Number, default: 3 }
})
</script>

<style scoped>
/* 骨架块 + 流光动画：浅底 + 自左向右扫过的高光，比纯 animate-pulse 更顺滑 */
.sk {
  position: relative;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.06);
  border-radius: 0.5rem;
}
.sk::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.7),
    transparent
  );
  animation: sk-shimmer 1.5s ease-in-out infinite;
}
@keyframes sk-shimmer {
  100% {
    transform: translateX(100%);
  }
}
</style>
