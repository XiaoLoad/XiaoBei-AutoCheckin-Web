// 折叠面板高度补间（列表详情与「正在进行」卡片详情共用）。
// 关键：纵向 padding 必须与 height 一起归零并补间，否则收起后会残留一段空白；
// 完成后 clearProps 交还类上的 py-*，避免内联样式覆盖后续主题/响应式变化。
// 用法：
//   const { onEnter, onLeave } = useCollapseTransition(() => reduceMotion.value, { pad: 16 })
//   <Transition :css="false" @enter="onEnter" @leave="onLeave">
import { gsap } from 'gsap'

export function useCollapseTransition(isReduced, { pad = 16, duration = 0.36 } = {}) {
  function onEnter(el, done) {
    if (isReduced()) {
      done()
      return
    }
    gsap.fromTo(
      el,
      { height: 0, paddingTop: 0, paddingBottom: 0, autoAlpha: 0 },
      {
        height: 'auto',
        paddingTop: pad,
        paddingBottom: pad,
        autoAlpha: 1,
        duration,
        ease: 'power2.out',
        onComplete: () => {
          gsap.set(el, { clearProps: 'height,paddingTop,paddingBottom' })
          done()
        },
      }
    )
    // 内容块错落入场，与列表详情同款节奏
    const items = el.querySelectorAll('[data-detail-item]')
    if (items.length) {
      gsap.fromTo(
        items,
        { autoAlpha: 0, y: 8 },
        {
          autoAlpha: 1,
          y: 0,
          duration: 0.32,
          stagger: 0.06,
          delay: 0.1,
          ease: 'power2.out',
          overwrite: true,
          clearProps: 'opacity,transform',
        }
      )
    }
  }

  function onLeave(el, done) {
    if (isReduced()) {
      done()
      return
    }
    gsap.to(el, {
      height: 0,
      paddingTop: 0,
      paddingBottom: 0,
      autoAlpha: 0,
      duration: 0.28,
      ease: 'power2.in',
      onComplete: done,
    })
  }

  return { onEnter, onLeave }
}
