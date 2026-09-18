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
    // ⚠️起点不能写死 0：收起没走完就再展开时（Transition 的 leave 被打断、元素尚未卸载）
    // 元素正停在中途，从 0 重播会先整块塌下去再撑开——视觉上就是闪一下。起值取当前内联值
    // （全新挂载时内联值为空、起值恰为 0，与原行为一致）；而打断时带内联 height 就量不到自然
    // 盒高，故先记起值、摘掉内联值再量目标高。
    const fromHeight = parseFloat(el.style.height) || 0
    const fromPad = parseFloat(el.style.paddingTop) || 0
    const fromAlpha = el.style.opacity === '' ? 0 : parseFloat(el.style.opacity)
    const interrupted = fromHeight > 0
    // ⚠️必须掐掉可能还在跑的 leave 补间：leave 被打断时 Vue 只是取消了自己的回调，
    // 我们那条 gsap.to(height:0) 仍在跑，会和这条 enter 补间抢同一个 height（谁后写谁生效），
    // 表现为回弹过程中抖动、且末态不定。另两个折叠实现（GCollapse / ImageLibrary）都显式 kill 了。
    gsap.killTweensOf(el)
    gsap.set(el, { clearProps: 'height,paddingTop,paddingBottom' })
    const target = el.getBoundingClientRect().height
    gsap.fromTo(
      el,
      { height: fromHeight, paddingTop: fromPad, paddingBottom: fromPad, autoAlpha: fromAlpha },
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
    // 内容块错落入场，与列表详情同款节奏；打断重现时不再重播——内容本就在原位，
    // 重播会让它们先整批消失再逐条淡回，与容器的回弹叠在一起更像闪。
    const items = el.querySelectorAll('[data-detail-item]')
    if (items.length && !interrupted) {
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
    // 同理掐掉还在跑的 enter 补间，否则它会一直把 height 往自然高拽、与收起方向对拉
    gsap.killTweensOf(el)
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
