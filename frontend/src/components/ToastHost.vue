<template>
  <!-- 全局 Toast 宿主：挂载到 body，独立于任何布局，保证守卫等任意位置都能触发。
       队列渲染（utils/toast.js）：同屏最多 3 条、各自计时，连发不再互相覆盖。
       样式与全站卡片语言同源：实心主题卡（bg-card 随主题）+ 环形图标章承载语义色，
       文字恒为 ink 保证可读；语义色只落在图标章上，不再使用半透明色调底。
       动画：GSAP JS 钩子驱动（:css="false"）——
         入场：自顶部 -24px 坠落 + back.out(2) 回弹过冲，干脆的"弹出"手感；
         离场：上飘淡出微缩（power2.in），离场瞬间绝对定位锁定宽度，其余补位平滑；
       全部动效尊重 prefers-reduced-motion（瞬时出现/消失）。 -->
  <Teleport to="body">
    <div class="pointer-events-none fixed left-1/2 top-6 z-[100] flex -translate-x-1/2 flex-col items-center gap-2">
      <TransitionGroup
        name="toast"
        :css="false"
        @before-enter="onBeforeEnter"
        @enter="onEnter"
        @leave="onLeave"
      >
        <div
          v-for="t in toastState.list"
          :key="t.id"
          class="flex items-center gap-3 rounded-2xl bg-card py-2.5 pl-2.5 pr-5 shadow-[0_1px_2px_rgba(20,33,61,0.06),0_18px_40px_-18px_rgba(20,33,61,0.4)] ring-1 ring-ink/5"
          role="alert"
        >
          <span class="grid h-8 w-8 shrink-0 place-items-center rounded-full" :class="iconWrapCls(t.type)" aria-hidden="true">
            <Icon :name="iconName(t.type)" :size="16" />
          </span>
          <span class="text-sm font-medium text-ink">{{ t.message }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { gsap } from 'gsap'
import { toastState } from '@/utils/toast'
import Icon from '@/components/Icon.vue'

const REDUCED_MOTION =
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

// 语义色只落在图标章：成功绿 / 错误红 / 警告琥珀 / 信息品牌蓝
function iconWrapCls(type) {
  switch (type) {
    case 'error':
      return 'bg-danger/10 text-danger'
    case 'success':
      return 'bg-success/10 text-success'
    case 'warning':
      return 'bg-warning/10 text-warning'
    default:
      return 'bg-brand/10 text-brand'
  }
}

function iconName(type) {
  switch (type) {
    case 'success':
      return 'check-circle'
    case 'error':
      return 'x-circle'
    case 'warning':
      return 'alert'
    default:
      return 'info'
  }
}

// ── GSAP 进出场钩子（:css="false"，Vue 等待 done 回调后才卸载元素） ──

// 入场前置：置初始态（顶部上方、微缩、透明）
function onBeforeEnter(el) {
  if (REDUCED_MOTION) return
  gsap.set(el, { autoAlpha: 0, y: -24, scale: 0.9 })
}

// 入场：坠落 + back.out 回弹过冲（缩放短暂越过 1 再回正，"弹出"手感）
function onEnter(el, done) {
  if (REDUCED_MOTION) {
    done()
    return
  }
  gsap.to(el, {
    autoAlpha: 1,
    y: 0,
    scale: 1,
    duration: 0.45,
    ease: 'back.out(2)',
    onComplete: done,
    clearProps: 'transform',
  })
}

// 离场：上飘淡出微缩；瞬间切绝对定位锁定原宽度，避免列表跳动（其余条目由
// TransitionGroup 的 move 补位机制平滑上移）
function onLeave(el, done) {
  if (REDUCED_MOTION) {
    done()
    return
  }
  el.style.pointerEvents = 'none'
  gsap.set(el, { position: 'absolute', left: '50%', xPercent: -50, width: el.offsetWidth })
  gsap.to(el, {
    autoAlpha: 0,
    y: -14,
    scale: 0.92,
    duration: 0.22,
    ease: 'power2.in',
    onComplete: done,
  })
}
</script>

<style scoped>
/* 离场项脱离文档流后，其余 toast 的补位位移（TransitionGroup FLIP 的 move 类） */
.toast-move {
  transition: transform 0.25s ease;
}
</style>
