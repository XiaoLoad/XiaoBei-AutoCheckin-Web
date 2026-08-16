<template>
  <div ref="root" class="g-collapse">
    <div ref="inner"><slot /></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { gsap } from 'gsap'

// 折叠容器：用 GSAP 把高度在 0 与内容实际高度之间平滑动画。
// 关键修正：挂载时同步展开（不依赖动画，直接 height:auto）；切换时等 DOM 更新后再测量，
// 避免 v-if/v-else 内容切换时量到旧高度、以及 GSAP height:'auto' 在某些情况下不生效导致内容卡在 0 高度不显示。
const props = defineProps({
  show: { type: Boolean, default: true },
  duration: { type: Number, default: 0.3 }
})

const root = ref(null)
const inner = ref(null)
let tween = null

function setExpanded() {
  const el = root.value
  if (!el) return
  if (tween) {
    tween.kill()
    tween = null
  }
  // 直接置 auto，GSAP height:'auto' 在某些版本/时机下不可靠，这里用原生兜底确保内容一定可见
  el.style.height = 'auto'
  el.style.opacity = '1'
  el.style.pointerEvents = 'auto'
}

function setCollapsed() {
  const el = root.value
  if (!el) return
  if (tween) {
    tween.kill()
    tween = null
  }
  el.style.height = '0px'
  el.style.opacity = '0'
  el.style.pointerEvents = 'none'
}

function toExpanded(animate) {
  const el = root.value
  const content = inner.value
  if (!el || !content) return
  if (tween) {
    tween.kill()
    tween = null
  }
  el.style.pointerEvents = 'auto'
  if (!animate) {
    setExpanded()
    return
  }
  const target = content.offsetHeight
  tween = gsap.fromTo(
    el,
    { height: 0, opacity: 0 },
    {
      height: target,
      opacity: 1,
      duration: props.duration,
      ease: 'power2.out',
      onComplete: () => {
        setExpanded()
        tween = null
      }
    }
  )
}

function toCollapsed(animate) {
  const el = root.value
  if (!el) return
  if (tween) {
    tween.kill()
    tween = null
  }
  if (!animate) {
    setCollapsed()
    return
  }
  const start = el.offsetHeight
  el.style.height = start + 'px'
  tween = gsap.fromTo(
    el,
    { height: start, opacity: 1 },
    {
      height: 0,
      opacity: 0,
      duration: props.duration,
      ease: 'power2.in',
      onComplete: () => {
        setCollapsed()
        tween = null
      }
    }
  )
}

onMounted(() => {
  if (props.show) setExpanded()
  else setCollapsed()
})

// 等 DOM（含 v-if/v-else 切换后的新内容）更新完成再测量，避免量到旧高度
watch(
  () => props.show,
  (v) => {
    nextTick(() => (v ? toExpanded(true) : toCollapsed(true)))
  }
)

onBeforeUnmount(() => {
  if (tween) tween.kill()
})
</script>

<style scoped>
.g-collapse {
  overflow: hidden;
}
</style>
