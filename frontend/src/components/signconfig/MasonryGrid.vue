<script>
// 瀑布流容器（JS 驱动，非 CSS columns）。
// 痛点：CSS columns 会在任意卡片高度变化时由浏览器重新平衡列分布，
// 导致卡片跨列重排、位置抖动。
// 本实现：列分配（卡片归属哪一列、列内顺序）仅在「挂载 / 断点变化 / 区块数量变化 / 显式刷新」时计算一次并固定；
// 日常内容高度变化（如凭证新增）只重算同一列内的纵向偏移以避免重叠，绝不让卡片跨列重排，从而稳定位置。
// 底部对齐：仅把每列「末张卡片」用 min-height 拉伸到统一的静止底边，使卡片底边本身落在同一条水平线；
// 用 min-height 而非 height —— 内容短则底部留白对齐、内容增长超出底边时自动撑高（绝不溢出），
// 因此展开态下某卡超出底边只是「临时不统一」，收回（内容减少）后自然回到统一底边。
import { h, ref, onMounted, onActivated, onBeforeUnmount, nextTick, watch } from 'vue'

const GAP = 16

export default {
  name: 'MasonryGrid',
  props: {
    // 单列的目标列宽（px）：容器宽度 ÷ 该值 ≈ 列数，实现"宽度自适应"的多列瀑布流
    minColWidth: { type: Number, default: 380 },
    // 列数上限，避免超宽屏列数过多
    maxCols: { type: Number, default: 3 }
  },
  setup(props, { slots, expose }) {
    const rootRef = ref(null)
    const itemEls = []
    const styles = ref([]) // 每张卡片的内联定位样式 {left,top,width,height,minHeight,visibility}
    const containerHeight = ref(0)

    let colOf = [] // 固定：第 i 张卡片归属的列
    let currentCols = 1
    let currentColWidth = 0
    let frozenBottom = 0 // 静止态底边：结构变化/刷新时重算，内容增减时冻结
    let ro = null
    let isRelayouting = false
    let rafId = null

    function getSlotList() {
      return (slots.default?.() || []).filter((v) => v && v.type)
    }
    function getCols() {
      const w = rootRef.value?.clientWidth || 0
      if (w <= 0) return 1
      const cols = Math.floor((w + GAP) / (props.minColWidth + GAP))
      return Math.max(1, Math.min(props.maxCols, cols))
    }
    function measureHeights() {
      return itemEls.map((el) => (el ? el.offsetHeight : 0))
    }

    // full=true 时重新计算列分配与静止底边；full=false 时仅按固定 colOf 重算同一列内偏移
    async function relayout(full) {
      if (!rootRef.value) return
      const list = getSlotList()
      const n = list.length
      if (n === 0) {
        containerHeight.value = 0
        styles.value = []
        return
      }
      const w = rootRef.value.clientWidth
      const cols = getCols()
      const colWidth = (w - GAP * (cols - 1)) / cols

      isRelayouting = true
      // 测量：全部 height:auto、隐藏态，量到内容真实高度（min-height 不反喂进测量，避免回环）
      styles.value = list.map(() => ({
        left: '0px',
        top: '0px',
        width: colWidth + 'px',
        height: 'auto',
        visibility: 'hidden'
      }))
      await nextTick()
      const heights = measureHeights()
      const recompute = full || colOf.length !== n
      const colHeights = new Array(cols).fill(0)
      const colLast = new Array(cols).fill(-1) // 每列末张卡片索引
      const colLastTop = new Array(cols).fill(0) // 每列末张卡片的 top
      const ns = []

      if (recompute) colOf = new Array(n).fill(0)
      list.forEach((_, i) => {
        let c
        if (recompute) {
          c = 0
          for (let k = 1; k < cols; k++) if (colHeights[k] < colHeights[c]) c = k
          colOf[i] = c
        } else {
          c = colOf[i] || 0
        }
        const top = colHeights[c]
        ns[i] = {
          left: c * (colWidth + GAP) + 'px',
          top: top + 'px',
          width: colWidth + 'px',
          height: 'auto',
          visibility: 'visible'
        }
        colHeights[c] += (heights[i] || 0) + GAP
        colLast[c] = i
        colLastTop[c] = top
      })

      const actualMax = Math.max(0, Math.max(...colHeights) - GAP)
      // 仅结构变化（重分配列 / 显式刷新）才重算静止底边；内容增减时冻结，
      // 避免「展开一张卡片」把其它卡片也撑高留白
      if (recompute || full) frozenBottom = actualMax

      // 仅拉伸每列「末张卡片」到静止底边：用 min-height 而非固定 height —— 内容短则卡片底边撑到
      // 静止线、底部对齐统一；内容增长超出底边时卡片随内容自然撑高（min-height 是下界、盒子真实增高），
      // 绝不溢出，且 ResizeObserver 会正常触发重排；此时该列临时超出统一线，收回（内容减少）后自然回落。
      let maxBottom = 0
      for (let c = 0; c < cols; c++) {
        const li = colLast[c]
        if (li === -1) continue
        const desired = frozenBottom - colLastTop[c]
        const natural = heights[li] || 0
        if (natural <= desired) {
          // 内容短：以 min-height 拉伸到静止线，内层卡片借 flex:1 填满，底边齐平
          ns[li] = { ...ns[li], minHeight: desired + 'px' }
          maxBottom = Math.max(maxBottom, frozenBottom)
        } else {
          // 内容已超出静止线：不拉伸，卡片按自然高度，该列底临时超出统一线
          maxBottom = Math.max(maxBottom, colLastTop[c] + natural)
        }
      }
      containerHeight.value = Math.max(0, maxBottom - GAP)
      currentCols = cols
      currentColWidth = colWidth
      styles.value = ns
      await nextTick()
      isRelayouting = false
    }

    // 内容高度变化：只重算同列偏移，不重新分配列
    function onResizeObserve() {
      if (isRelayouting) return
      if (rafId) cancelAnimationFrame(rafId)
      rafId = requestAnimationFrame(() => {
        rafId = null
        relayout(false)
      })
    }
    function onWindowResize() {
      if (!rootRef.value) return
      const newCols = getCols()
      relayout(newCols !== currentCols) // 断点变化才重分配列，否则只按新宽度重排
    }

    onMounted(async () => {
      await nextTick()
      await relayout(true)
      ro = new ResizeObserver(onResizeObserve)
      itemEls.forEach((el) => {
        if (el) ro.observe(el)
      })
      window.addEventListener('resize', onWindowResize)
    })
    // keep-alive 重新激活该 Tab 时，DOM 已脱离文档又被重新插入，需按当前宽度重排一次
    onActivated(() => {
      if (!isRelayouting) relayout(true)
    })
    onBeforeUnmount(() => {
      if (ro) ro.disconnect()
      window.removeEventListener('resize', onWindowResize)
      if (rafId) cancelAnimationFrame(rafId)
    })

    // 区块数量变化（如某 section 出现/消失）时整体重排一次
    watch(
      () => getSlotList().length,
      () => {
        if (!isRelayouting) relayout(true)
      }
    )

    // 供父组件在需要时显式刷新排列（如切换配置套后强制重算静止底边）
    function refresh() {
      relayout(true)
    }
    expose({ refresh })

    return () => {
      const list = getSlotList()
      return h(
        'div',
        {
          ref: rootRef,
          class: 'xb-masonry',
          style: { position: 'relative', width: '100%', height: containerHeight.value + 'px' }
        },
        list.map((vnode, i) =>
          h(
            'div',
            {
              key: 'mg-' + i,
              class: 'xb-masonry-item',
              style: { position: 'absolute', top: 0, left: 0, boxSizing: 'border-box', ...(styles.value[i] || {}) },
              ref: (el) => {
                itemEls[i] = el
              }
            },
            [vnode]
          )
        )
      )
    }
  }
}
</script>

<style>
.xb-masonry {
  width: 100%;
}
.xb-masonry-item {
  box-sizing: border-box;
  /* 用 flex 列让内部卡片在 min-height 拉伸时仍能填满包裹层，底边齐平且不溢出 */
  display: flex;
  flex-direction: column;
}
.xb-masonry-item > * {
  flex: 1 1 auto;
  min-height: 0;
}
</style>
