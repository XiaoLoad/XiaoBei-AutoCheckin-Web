<template>
  <!-- 全局顶部加载条（App 级唯一实例）：视口顶部 3px 品牌色滑动进度条。
       可见性取两个来源的并集：
         ① refreshBus —— 各 store 的静默刷新与抽屉/组件的局部异步（含非 HTTP 的整备工作）；
         ② loadingBar —— HTTP 层按请求计数，覆盖首屏加载、翻页筛选、抽屉与模态框取数、
            二级页面，不再只有走总线的静默刷新才有反应。
       与数据区降透明配合使用——降透明表达"内容在更新"，本条表达"正在加载"。 -->
  <div
    v-if="visible"
    class="pointer-events-none fixed inset-x-0 top-0 z-[1200] h-[3px] overflow-hidden"
    aria-hidden="true"
  >
    <div class="refresh-strip h-full w-2/5 rounded-r-full bg-brand shadow-[0_0_8px_rgba(37,99,235,0.55)]"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRefreshBusStore } from '@/stores/refreshBus'
import { loadingBarShown } from '@/utils/loadingBar'

const refreshBus = useRefreshBusStore()
const visible = computed(() => refreshBus.active || loadingBarShown.value)
</script>

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
