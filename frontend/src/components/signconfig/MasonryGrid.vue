<script>
// 瀑布流容器（JS 驱动，非 CSS columns）。
// 痛点：CSS columns 会在任意卡片高度变化时由浏览器重新平衡列分布，
// 导致卡片跨列重排、位置抖动。
// 本实现：列分配（卡片归属哪一列、列内顺序）仅在「挂载 / 断点变化 / 区块数量变化 / 显式刷新」时计算一次并固定；
// 日常内容高度变化（如凭证新增）只重算同一列内的纵向偏移以避免重叠，绝不让卡片跨列重排，从而稳定位置。
//
// 列高策略：自然错落（经典瀑布流）——卡片高度完全由内容决定，不做底边强制对齐。
// 此前版本会把每列末卡用 min-height 拉伸到统一静止底边：内容短的卡被撑高出现
// 大片卡内留白，且任一卡展开超出冻结底边时该列凸出、底边错落，观感不佳，故移除。
//
// GSAP 位移补间（FLIP）：布局重算前后各记录一次卡片位置，位置变化的卡片用
// transform 从旧位平滑滑到新位（0.35s power2.out），不与 left/top 内联绑定冲突；
// 配合 GCollapse 的高度折叠动画，展开/收起/重排时整列行云流水。
// 首次布局后卡片轻错落淡入（仅一次，keep-alive 重激活不重复播）。
// 全部动效尊重 prefers-reduced-motion。
import { h, ref, onMounted, onActivated, onBeforeUnmount, nextTick, watch } from 'vue'
import { gsap } from 'gsap'

const GAP = 16
const REDUCED_MOTION =
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

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
    const styles = ref([]) // 每张卡片的内联定位样式 {left,top,width,visibility}
    const containerHeight = ref(0)

    let colOf = [] // 固定：第 i 张卡片归属的列
    let currentCols = 1
    let ro = null
    let isRelayouting = false
    let rafId = null
    let entranceDone = false

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

    // full=true 时重新计算列分配；full=false 时仅按固定 colOf 重算同一列内偏移
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

      // FLIP 第一步：记录重排前每张卡的实际位置（内联样式即上一次布局的结果；
      // 元素已脱离文档（keep-alive 收起）时跳过，避免陈旧位置引发怪异滑动）
      const oldPos = itemEls.map((el) =>
        el && el.isConnected ? { left: parseFloat(el.style.left) || 0, top: parseFloat(el.style.top) || 0 } : null
      )

      isRelayouting = true
      // 测量：全部 height:auto、隐藏态，量到内容真实高度
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
        ns[i] = {
          left: c * (colWidth + GAP) + 'px',
          top: colHeights[c] + 'px',
          width: colWidth + 'px',
          height: 'auto',
          visibility: 'visible'
        }
        colHeights[c] += (heights[i] || 0) + GAP
      })

      containerHeight.value = Math.max(0, Math.max(...colHeights) - GAP)
      currentCols = cols
      styles.value = ns
      await nextTick()

      // FLIP 第二步：位置变化的卡片从旧位平滑滑到新位（transform 补间，
      // 与 left/top 内联绑定互不干扰，动画结束清 transform）
      if (!REDUCED_MOTION) {
        list.forEach((_, i) => {
          const el = itemEls[i]
          const old = oldPos[i]
          if (!el || !old || !el.isConnected) return
          const dx = old.left - (parseFloat(ns[i].left) || 0)
          const dy = old.top - (parseFloat(ns[i].top) || 0)
          if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return
          gsap.fromTo(
            el,
            { x: dx, y: dy },
            { x: 0, y: 0, duration: 0.35, ease: 'power2.out', clearProps: 'transform' }
          )
        })
      }

      // 首次布局入场：卡片轻错落淡入（仅挂载后第一次；keep-alive 重激活不重复播）
      if (!entranceDone) {
        entranceDone = true
        if (!REDUCED_MOTION) {
          const els = itemEls.filter(Boolean)
          if (els.length) {
            gsap.fromTo(
              els,
              { autoAlpha: 0, y: 10 },
              { autoAlpha: 1, y: 0, duration: 0.4, stagger: 0.05, ease: 'power2.out', clearProps: 'opacity,visibility,transform' }
            )
          }
        }
      }

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

    // 供父组件在需要时显式刷新排列（如切换配置套后强制重算）
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
}
</style>
