// 登录页 GSAP 动画逻辑封装
// 设计原则（遵循 gsap-frameworks 规范）：
//  1. 所有动画在 onMounted 后、DOM 就绪时创建；
//  2. 使用 gsap.context(scope) 将选择器作用域限定在当前组件根节点，避免影响页面其它部分；
//  3. context 在 onUnmounted 时调用 revert()，统一回收所有 tween 与事件监听，避免内存泄漏；
//  4. 循环类环境动效（光晕/圆环/光点）交给 CSS keyframes 处理，组件卸载即停止，无需手动清理；
//  5. 尊重 prefers-reduced-motion，减少动态用户的不适；
//  6. 防御性：入场动画只做"叠加效果"，绝不让元素永久停留在隐藏态——动画完成/中断/异常/超时
//     都会强制清除内联样式回到 CSS 默认可见态，避免登录按钮等关键元素卡在 visibility:hidden。
//
// ⚠️ 入场一律「先用 gsap.set 铺初值，时间线里全程 to()」，不要用 from() / fromTo()：
//    from() 要到**创建那一刻**才去读元素的当前值当终值，而它的初值又是立即渲染的。
//    同一条时间线上只要同一属性已被别的补间写过、或该补间被重渲染过，终值就会等于初值，
//    补间退化成空转。实测登录按钮正是这样：写进去的初值与终值都是
//    { opacity:0, y:14, scale:0.98 }，整条时间线跑完都没动过，一直停在 visibility:hidden，
//    直到 onComplete 的 clearProps 清掉内联样式它才出现 —— 表现成
//    「其它元素入场完之后，按钮还要再等 1~2 秒才出来」。
import { onMounted, onUnmounted } from 'vue'
import { gsap } from 'gsap'

// 所有参与入场动画的目标选择器
const ENTER_TARGETS = ['.brand-panel', '.brand-mark', '.brand-line', '.brand-check', '.login-card', '.login-field']
// 表单字段（不含登录按钮）——按钮单独排期，让它紧跟在最后一个字段之后入场
const FIELD_SELECTOR = '.login-field:not(.login-submit)'
const SUBMIT_SELECTOR = '.login-submit'

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
        // 捕获根节点引用：onUnmounted 时 rootRef.value 会被 Vue 置空，
        // 若清理闭包里直接读 rootRef.value 会触发 "Cannot read properties of null"，
        // 故在此处把当前 DOM 节点存到局部变量，后续增删监听都用它。
        const rootEl = rootRef.value
        const cleanup = []

        if (reduceMotion) {
          // 减弱动效：直接呈现最终态，连初值都不铺
          return () => cleanup.forEach((fn) => fn())
        }

        // —— 铺初值 ——
        // 集中在这里一次写完，后面时间线只做「从当前值补到终值」，与 from() 的时序解耦。
        gsap.set(rootEl, { autoAlpha: 0 })
        gsap.set('.brand-panel', { autoAlpha: 0, x: -44 })
        gsap.set('.brand-mark', { autoAlpha: 0, scale: 0.84 })
        gsap.set('.brand-line', { autoAlpha: 0, y: 18 })
        gsap.set('.brand-check', { strokeDashoffset: 1 })
        gsap.set('.login-card', { autoAlpha: 0, y: 28 })
        gsap.set(FIELD_SELECTOR, { autoAlpha: 0, y: 16 })
        gsap.set(SUBMIT_SELECTOR, { autoAlpha: 0, y: 14, scale: 0.98 })

        // —— 入场时间线 ——
        // 同时长排期，节奏说明：
        //   · 左侧品牌面板 0~1.4s：标记与对勾画完收尾
        //   · 右侧卡片 0.16~0.78s，字段 0.34s 起按 0.07s 错峰，最后一个字段 1.26s 落定
        //   · 登录按钮排在「它上面那行字段」之后（0.74s 起，0.3s 内的快节奏），
        //     1.04s 就位 —— 全程在时间线结束之前，不再等所有人入场完才出现
        // onComplete / onInterrupt 都强制清除内联样式，确保元素回到 CSS 默认（可见）状态，
        // 杜绝 HMR 残留或动画中断导致按钮等关键元素永久隐藏。
        const tl = gsap.timeline({
          defaults: { ease: 'power3.out' },
          onComplete: ensureVisible,
          onInterrupt: ensureVisible
        })
        tl.to(rootEl, { autoAlpha: 1, duration: 0.35 }, 0)
          .to('.brand-panel', { autoAlpha: 1, x: 0, duration: 0.6 }, 0)
          .to('.brand-mark', { autoAlpha: 1, scale: 1, duration: 0.7, ease: 'back.out(1.5)' }, 0.12)
          .to('.brand-line', { autoAlpha: 1, y: 0, stagger: 0.07, duration: 0.5 }, 0.24)
          .to('.brand-check', { strokeDashoffset: 0, duration: 0.9, ease: 'power2.inOut' }, 0.5)
          .to('.login-card', { autoAlpha: 1, y: 0, duration: 0.62 }, 0.16)
          .to(FIELD_SELECTOR, { autoAlpha: 1, y: 0, stagger: 0.07, duration: 0.5 }, 0.34)
          .to(SUBMIT_SELECTOR, { autoAlpha: 1, y: 0, scale: 1, duration: 0.3, ease: 'power2.out' }, 0.74)

        // —— 输入框聚焦微动效 ——
        const onFocusIn = (e) => {
          const field = e.target.closest('.login-field')
          if (field) gsap.to(field, { y: -2, duration: 0.3, ease: 'power2.out' })
        }
        const onFocusOut = (e) => {
          const field = e.target.closest('.login-field')
          if (field) gsap.to(field, { y: 0, duration: 0.35, ease: 'power2.out' })
        }
        rootEl.addEventListener('focusin', onFocusIn)
        rootEl.addEventListener('focusout', onFocusOut)
        cleanup.push(() => {
          rootEl.removeEventListener('focusin', onFocusIn)
          rootEl.removeEventListener('focusout', onFocusOut)
        })

        // —— 登录按钮 hover 微交互 ——
        // overwrite: 'auto' 让新补间接手同一属性上的旧补间，避免连点/快速划过时互相拉扯
        const btn = rootEl.querySelector(SUBMIT_SELECTOR)
        if (btn) {
          const enter = () => gsap.to(btn, { scale: 1.02, duration: 0.25, ease: 'power2.out', overwrite: 'auto' })
          const leave = () => gsap.to(btn, { scale: 1, duration: 0.3, ease: 'power2.out', overwrite: 'auto' })
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

    // 安全网：入场动画最长约 1.4s，2.2s 后强制清除内联样式，
    // 防御 rAF 节流 / HMR 残留等极端情况下元素卡在隐藏起始态。
    fallbackTimer = setTimeout(ensureVisible, 2200)
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
