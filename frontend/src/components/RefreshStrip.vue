<template>
  <!-- 静默刷新期的全局感知提示：视口顶部 3px 品牌色滑动进度条。
       与数据区的降透明配合使用——降透明表达"内容在更新"，本条表达"正在刷新"。 -->
  <div class="pointer-events-none fixed inset-x-0 top-0 z-[1200] h-[3px] overflow-hidden" aria-hidden="true">
    <div class="refresh-strip h-full w-2/5 rounded-r-full bg-brand shadow-[0_0_8px_rgba(37,99,235,0.55)]"></div>
  </div>
</template>

<style scoped>
.refresh-strip {
  animation: refresh-slide 1.1s ease-in-out infinite;
}
@keyframes refresh-slide {
  from { transform: translateX(-100%); }
  to { transform: translateX(350%); }
}
@media (prefers-reduced-motion: reduce) {
  .refresh-strip { animation: none; opacity: 0.75; }
}
</style>
