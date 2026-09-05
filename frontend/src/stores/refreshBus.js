// 全局刷新总线（Pinia）：任何 store 的静默刷新与抽屉/组件的局部异步在
// begin/end 之间登记，App 级唯一的 RefreshStrip 由「活跃刷新数 > 0」驱动，
// 使跨页面、跨抽屉触发的加载（如抽屉里保存后回写另一页 store）都有统一的
// 顶部进度条感知。原各视图内嵌的 RefreshStrip 已移除，数据区降透明仍由
// 各视图自己的 refreshing 标志驱动，两者语义互补：条=正在刷新、降透明=内容在更新。
//
// 并发语义：计数制，支持嵌套与并发登记（多个 store 同时刷新只亮一条）；
// end 必须与 begin 一一配对——被竞态守卫淘汰的请求也在 finally 无条件 end，
// 防止计数泄漏导致进度条永不熄灭。
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useRefreshBusStore = defineStore('refreshBus', () => {
  const count = ref(0)
  const active = computed(() => count.value > 0)

  function begin() {
    count.value += 1
  }

  function end() {
    count.value = Math.max(0, count.value - 1)
  }

  // 包装一次异步登记：begin → 执行 → 无论成败 end，适合抽屉局部加载直接接入
  async function run(task) {
    begin()
    try {
      return await task()
    } finally {
      end()
    }
  }

  return { count, active, begin, end, run }
})
