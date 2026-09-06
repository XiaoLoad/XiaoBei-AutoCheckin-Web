<template>
  <!-- 瀑布流容器：原生 slot + DOM 直接定位。
       设计要点（为什么不用渲染函数包装槽位 vnode）：
       - 包装式实现需要以位置 key 重建子元素列表，在区块增减（v-if 切换）时
         Vue 的 keyed 卸载会拿到 null vnode 直接崩，渲染中断把布局冻在测量态；
       - 本实现由 Vue 自行管理子元素补丁，组件只负责测量子元素与写入内联定位
         （子元素根节点均无动态 style 绑定，内联样式不会被 Vue 覆盖）；
       - 子元素列表变化用 MutationObserver 感知（childList），内容高度变化用
         ResizeObserver 感知（仅同列内重排，不跨列移动卡片）。
       列高策略：自然错落（经典瀑布流）——卡片高度由内容决定，底部不做强制对齐，
       顶部对齐是固有属性（所有列从容器顶部 0 起排）。
       GSAP：位置变化 FLIP 补间（0.35s power2.out）+ 首次布局轻错落淡入（仅一次），
       全部动效尊重 prefers-reduced-motion。 -->
  <div ref="rootRef" class="xb-masonry" :style="{ position: 'relative', width: '100%', height: containerHeight + 'px' }">
    <slot />
  </div>
</template>

<script>
import { ref, onMounted, onActivated, onBeforeUnmount, nextTick } from 'vue'
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
  setup(props) {
    const rootRef = ref(null)
    const containerHeight = ref(0)

    let colOf = []        // 第 i 个子元素归属的列（仅 full 重排时重新分配）
    let currentCols = 1
    let ro = null
    let mo = null
    let rafId = null
    let isRelayouting = false
    let entranceDone = false
    // 旧位置快照（WeakMap：元素 → {left,top}），供 FLIP 补间计算位移
    const lastPos = new WeakMap()

    function childEls() {
      return Array.from(rootRef.value?.children || []).filter((el) => el.nodeType === 1)
    }
    function getCols() {
      const w = rootRef.value?.clientWidth || 0
      if (w <= 0) return 1
      const cols = Math.floor((w + GAP) / (props.minColWidth + GAP))
      return Math.max(1, Math.min(props.maxCols, cols))
    }

    // full=true 重新分配列（最短列优先）；false 仅按固定 colOf 重排同列内偏移
    async function relayout(full) {
      if (!rootRef.value) return
      const els = childEls()
      const n = els.length
      if (n === 0) {
        containerHeight.value = 0
        colOf = []
        return
      }
      const w = rootRef.value.clientWidth
      const cols = getCols()
      const colWidth = Math.max(80, (w - GAP * (cols - 1)) / cols)

      // FLIP 第一步：记录重排前位置（脱离文档的元素跳过）
      const oldPos = els.map((el) => {
        const p = lastPos.get(el)
        return el.isConnected && p ? { ...p } : null
      })

      isRelayouting = true
      // 测量：锁定列宽 + 绝对定位 + 隐藏，量到内容真实高度
      els.forEach((el) => {
        el.style.position = 'absolute'
        el.style.width = colWidth + 'px'
        el.style.left = '0px'
        el.style.top = '0px'
        el.style.visibility = 'hidden'
      })
      await nextTick()
      const heights = els.map((el) => el.offsetHeight)
      const recompute = full || colOf.length !== n

      const colHeights = new Array(cols).fill(0)
      if (recompute) {
        colOf = new Array(n).fill(0)
        els.forEach((_, i) => {
          let c = 0
          for (let k = 1; k < cols; k++) if (colHeights[k] < colHeights[c]) c = k
          colOf[i] = c
          colHeights[c] += (heights[i] || 0) + GAP
        })
      } else {
        els.forEach((_, i) => {
          const c = colOf[i] || 0
          colHeights[c] += (heights[i] || 0) + GAP
        })
      }

      const tops = new Array(cols).fill(0)
      els.forEach((el, i) => {
        const c = colOf[i] || 0
        el.style.left = c * (colWidth + GAP) + 'px'
        el.style.top = tops[c] + 'px'
        el.style.visibility = 'visible'
        lastPos.set(el, { left: c * (colWidth + GAP), top: tops[c] })
        tops[c] += (heights[i] || 0) + GAP
      })
      containerHeight.value = Math.max(0, Math.max(...colHeights) - GAP)
      currentCols = cols
      await nextTick()

      // FLIP 第二步：位置变化的卡片从旧位平滑滑到新位
      if (!REDUCED_MOTION) {
        els.forEach((el, i) => {
          const old = oldPos[i]
          if (!old) return
          const dx = old.left - (parseFloat(el.style.left) || 0)
          const dy = old.top - (parseFloat(el.style.top) || 0)
          if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return
          gsap.fromTo(
            el,
            { x: dx, y: dy },
            { x: 0, y: 0, duration: 0.35, ease: 'power2.out', clearProps: 'transform' }
          )
        })
      }

      // 首次布局入场：卡片轻错落淡入（仅第一次；keep-alive 重激活不重复播）
      if (!entranceDone) {
        entranceDone = true
        if (!REDUCED_MOTION && els.length) {
          gsap.fromTo(
            els,
            { autoAlpha: 0, y: 10 },
            { autoAlpha: 1, y: 0, duration: 0.4, stagger: 0.05, ease: 'power2.out', clearProps: 'opacity,visibility,transform' }
          )
        }
      }

      isRelayouting = false
    }

    // 内容高度变化：只重算同列偏移，不跨列移动卡片
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
      relayout(newCols !== currentCols) // 断点变化才重分配列
    }

    onMounted(async () => {
      await nextTick()
      await relayout(true)
      ro = new ResizeObserver(onResizeObserve)
      childEls().forEach((el) => ro.observe(el))
      // 子元素列表变化（v-if 区块增减 / Tab 切换）→ 整体重排
      mo = new MutationObserver(() => {
        if (isRelayouting) return
        relayout(true).then(() => {
          childEls().forEach((el) => ro.observe(el))
        })
      })
      mo.observe(rootRef.value, { childList: true })
      window.addEventListener('resize', onWindowResize)
    })
    // keep-alive 重新激活：DOM 重新插入文档，按当前宽度重排一次
    onActivated(() => {
      if (!isRelayouting) relayout(true)
    })
    onBeforeUnmount(() => {
      if (ro) ro.disconnect()
      if (mo) mo.disconnect()
      window.removeEventListener('resize', onWindowResize)
      if (rafId) cancelAnimationFrame(rafId)
    })

    return { rootRef, containerHeight }
  }
}
</script>

<style>
.xb-masonry {
  width: 100%;
}
.xb-masonry > * {
  box-sizing: border-box;
}
</style>
