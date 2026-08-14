// 登录页 GSAP 动画逻辑封装
// 设计原则（遵循 gsap-frameworks 规范）：
//  1. 所有动画在 onMounted 后、DOM 就绪时创建；
//  2. 使用 gsap.context(scope) 将选择器作用域限定在当前组件根节点，避免影响页面其它部分；
//  3. context 在 onUnmounted 时调用 revert()，统一回收所有 tween 与事件监听，避免内存泄漏；
//  4. 循环类环境动效（光晕/圆环/光点）交给 CSS keyframes 处理，组件卸载即停止，无需手动清理；
//  5. 尊重 prefers-reduced-motion，减少动态用户的不适；
//  6. 防御性：入场动画只做"叠加效果"，绝不让元素永久停留在隐藏态——动画完成/中断/异常/超时
//     都会强制清除内联样式回到 CSS 默认可见态，避免登录按钮等关键元素卡在 visibility:hidden。
import { onMounted, onUnmounted, ref } from 'vue'
import { gsap } from 'gsap'

// 所有参与入场动画的目标选择器
const ENTER_TARGETS = ['.brand-panel', '.brand-mark', '.brand-line', '.login-card', '.login-field']

/**
 * 初始化登录页的所有入场与交互动画。
 * @param {import('vue').Ref<HTMLElement|null>} rootRef 组件根节点引用
 */
export function useLoginAnimations(rootRef) {
  let ctx = null
  let fallbackTimer = null
  const reduceMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  // 统一把动画元素恢复到可见终态（清除 GSAP 写入的内联样式）
  const ensureVisible = () => {
    try {
      gsap.set(ENTER_TARGETS, { clearProps: 'all' })
    } catch (e) {
      /* 忽略清理异常 */
    }
  }

  function play() {
    if (!rootRef.value) return
    try {
      ctx = gsap.context(() => {
        const cleanup = []

        if (reduceMotion) {
          // 减弱动效：直接呈现最终态，仅保留必要的可见性
          gsap.set(ENTER_TARGETS, { autoAlpha: 1, clearProps: 'transform' })
          return () => cleanup.forEach((fn) => fn())
        }

        // —— 入场时间线 ——
        // onComplete / onInterrupt 都强制清除内联样式，确保元素回到 CSS 默认（可见）状态，
        // 杜绝 HMR 残留或动画中断导致按钮等关键元素永久隐藏。
        const tl = gsap.timeline({
          defaults: { ease: 'power3.out' },
          onComplete: ensureVisible,
          onInterrupt: ensureVisible
        })
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
    } catch (e) {
      // 任何异常都绝不隐藏元素
      ensureVisible()
    }

    // 安全网：入场动画最长约 1.8s，2.8s 后强制清除内联样式，
    // 防御 rAF 节流 / HMR 残留等极端情况下元素卡在隐藏起始态。
    fallbackTimer = setTimeout(ensureVisible, 2800)
  }

  onMounted(() => {
    play()
  })

  onUnmounted(() => {
    // 回收所有 tween / timeline / 事件监听，避免内存泄漏
    if (fallbackTimer) clearTimeout(fallbackTimer)
    ctx?.revert()
  })
}
