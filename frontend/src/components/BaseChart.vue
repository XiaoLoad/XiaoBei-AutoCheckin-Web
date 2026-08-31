<template>
  <div ref="el" class="w-full" :style="height ? { height } : {}"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

// 按需注册：仅引入项目实际使用的图表类型与组件，避免全量 echarts 打包（体积从 ~1MB 降至数百 KB）
echarts.use([
  LineChart,
  BarChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  CanvasRenderer
])

const props = defineProps({
  // ECharts 配置项（完整 option）
  option: { type: Object, required: true },
  // 容器高度，默认撑满父级
  height: { type: String, default: '' }
})

const el = ref(null)
let chart = null
let ro = null

function prefersReducedMotion() {
  return typeof window !== 'undefined' && window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function apply() {
  if (!chart) return
  // 复制一份，避免直接改写传入对象；减弱动效时关闭动画
  const opt = JSON.parse(JSON.stringify(props.option))
  if (prefersReducedMotion()) opt.animation = false
  chart.setOption(opt, { notMerge: true })
}

onMounted(() => {
  chart = echarts.init(el.value, null, { renderer: 'canvas' })
  apply()
  ro = new ResizeObserver(() => chart && chart.resize())
  ro.observe(el.value)
})

// option 变化（含深层）时重绘
watch(() => props.option, apply, { deep: true })

onBeforeUnmount(() => {
  if (ro) { ro.disconnect(); ro = null }
  if (chart) { chart.dispose(); chart = null }
})
</script>
