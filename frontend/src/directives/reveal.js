// v-reveal：元素进入视口时淡入上移（GSAP + ScrollTrigger）。
// 用法：
//   单元素：  <article v-reveal>...</article>
//   容器错峰：<div v-reveal="{ stagger: 0.05 }"> ...子元素... </div>  → 子元素依次揭示
// 设计原则（对齐 useLoginAnimations / gsap-frameworks 规范）：
//   1. 用 gsap.context(scope) 限定作用域，unmount 时 revert() 统一回收 tween 与 ScrollTrigger，避免泄漏；
//   2. 自动探测最近的可滚动祖先作为 ScrollTrigger 的 scroller（卡片网格多在内部滚动容器里），
//      找不到则回落到 window，保证进入视口即触发；
//   3. clearProps:'all' 在动画结束后清除内联样式，避免残留 transform 覆盖 Tailwind 的 hover 位移；
//   4. 尊重 prefers-reduced-motion，直接呈现终态、不做位移动画；
//   5. 防御性：任何异常都绝不把元素留在隐藏态。
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

const reduceMotion =
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

// 向上查找最近的「可滚动祖先」，作为 ScrollTrigger 的 scroller。
function findScroller(el) {
  let node = el.parentElement
  while (node && node !== document.documentElement && node !== document.body) {
    const style = getComputedStyle(node)
    const oy = style.overflowY
    if ((oy === 'auto' || oy === 'scroll') && node.scrollHeight > node.clientHeight + 1) {
      return node
    }
    node = node.parentElement
  }
  return window
}

export default {
  mounted(el, binding) {
    if (reduceMotion) return
    const opts = binding.value || {}
    // 容器模式（传 stagger）揭示直接子元素；否则揭示元素自身
    const targets = opts.stagger ? Array.from(el.children) : [el]
    if (!targets.length) return

    try {
      const ctx = gsap.context(() => {
        gsap.from(targets, {
          autoAlpha: 0,
          y: opts.y ?? 16,
          duration: opts.duration ?? 0.5,
          ease: 'power2.out',
          stagger: opts.stagger || 0,
          clearProps: 'all',
          scrollTrigger: {
            trigger: el,
            scroller: findScroller(el),
            start: opts.start || 'top 92%',
            once: true
          }
        })
      })
      el.__revealCtx = ctx
    } catch (e) {
      // 异常即放弃动画，元素保持 CSS 默认可见态
      gsap.set(targets, { clearProps: 'all' })
    }
  },
  unmounted(el) {
    if (el.__revealCtx) {
      el.__revealCtx.revert()
      el.__revealCtx = null
    }
  }
}
