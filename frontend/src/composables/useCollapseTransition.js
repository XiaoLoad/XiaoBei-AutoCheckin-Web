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
    // ⚠️补间目标必须是**归零 padding 之前**量到的实际盒高，不能用 height:'auto'：
    // GSAP 是在 from 生效之后才解析 'auto' 的，那时 padding 已被归零，量出来的是内容高；
    // 而 Tailwind preflight 全局 box-sizing:border-box 会把这个数当盒高用，于是补间走到
    // 内容高便结束，clearProps 交还 padding 的瞬间盒子突然弹高 2×pad（实测 28px 的跳变）。
    // 先量再补间，终点与交还 padding 后的自然高度完全一致，没有任何跳变。
    const target = el.getBoundingClientRect().height
    gsap.fromTo(
      el,
      { height: 0, paddingTop: 0, paddingBottom: 0, autoAlpha: 0 },
      {
        height: target,
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
