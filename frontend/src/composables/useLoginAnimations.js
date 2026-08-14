// 登录页 GSAP 动画逻辑封装
// 设计原则（遵循 gsap-frameworks 规范）：
//  1. 所有动画在 onMounted 后、DOM 就绪时创建；
//  2. 使用 gsap.context(scope) 将选择器作用域限定在当前组件根节点，避免影响页面其它部分；
//  3. context 在 onUnmounted 时调用 revert()，统一回收所有 tween 与事件监听，避免内存泄漏；
//  4. 循环类环境动效（光晕/圆环/光点）交给 CSS keyframes 处理，组件卸载即停止，无需手动清理；
//  5. 尊重 prefers-reduced-motion，减少动态用户的不适。
import { onMounted, onUnmounted, ref } from 'vue'
import { gsap } from 'gsap'

/**
 * 初始化登录页的所有入场与交互动画。
 * @param {import('vue').Ref<HTMLElement|null>} rootRef 组件根节点引用
 */
export function useLoginAnimations(rootRef) {
  let ctx = null
  const reduceMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  function play() {
    if (!rootRef.value) return

    ctx = gsap.context(() => {
      const cleanup = []

      if (reduceMotion) {
        // 减弱动效：直接呈现最终态，仅保留必要的可见性
        gsap.set(
          ['.brand-panel', '.brand-mark', '.brand-line', '.login-card', '.login-field'],
          { autoAlpha: 1, clearProps: 'transform' }
        )
        return () => cleanup.forEach((fn) => fn())
      }

      // —— 入场时间线 ——
      const tl = gsap.timeline({ defaults: { ease: 'power3.out' } })
      tl.from(rootRef.value, { autoAlpha: 0, duration: 0.4 })
        .from('.brand-panel', { autoAlpha: 0, x: -44, duration: 0.65 }, 0)
        .from('.brand-mark', { scale: 0.84, autoAlpha: 0, duration: 0.8, ease: 'back.out(1.5)' }, 0.15)
        .from('.brand-line', { y: 18, autoAlpha: 0, stagger: 0.08, duration: 0.6 }, 0.28)
        .fromTo('.brand-check', { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 1.0, ease: 'power2.inOut' }, 0.55)
        .from('.login-card', { y: 28, autoAlpha: 0, duration: 0.7 }, 0.2)
        .from('.login-field', { y: 16, autoAlpha: 0, stagger: 0.09, duration: 0.6 }, 0.45)

      // —— 输入框聚焦微动效 ——
      const onFocusIn = (e) => {
        const field = e.target.closest('.login-field')
        if (field) gsap.to(field, { y: -2, duration: 0.3, ease: 'power2.out' })
      }
      const onFocusOut = (e) => {
        const field = e.target.closest('.login-field')
        if (field) gsap.to(field, { y: 0, duration: 0.35, ease: 'power2.out' })
      }
      rootRef.value.addEventListener('focusin', onFocusIn)
      rootRef.value.addEventListener('focusout', onFocusOut)
      cleanup.push(() => {
        rootRef.value.removeEventListener('focusin', onFocusIn)
        rootRef.value.removeEventListener('focusout', onFocusOut)
      })

      // —— 登录按钮 hover 微交互 ——
      const btn = rootRef.value.querySelector('.login-submit')
      if (btn) {
        const enter = () => gsap.to(btn, { scale: 1.02, duration: 0.25, ease: 'power2.out' })
        const leave = () => gsap.to(btn, { scale: 1, duration: 0.3, ease: 'power2.out' })
        btn.addEventListener('mouseenter', enter)
        btn.addEventListener('mouseleave', leave)
        cleanup.push(() => {
          btn.removeEventListener('mouseenter', enter)
          btn.removeEventListener('mouseleave', leave)
        })
      }

      return () => cleanup.forEach((fn) => fn())
    }, rootRef.value)
  }

  onMounted(() => {
    play()
  })

  onUnmounted(() => {
    // 回收所有 tween / timeline / 事件监听，避免内存泄漏
    ctx?.revert()
  })
}
