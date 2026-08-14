<template>
  <section>
    <h1 class="text-2xl font-bold text-gray-900">关于</h1>
    <p class="mt-2 text-gray-600 leading-relaxed">
      本项目为「小北寝室自动打卡」的 Web 端基础框架，采用前后端分离架构：
    </p>
    <ul class="mt-4 list-disc pl-6 space-y-1 text-gray-600">
      <li>前端：Vue 3 + Vite + TailwindCSS + axios + Pinia + Vue Router</li>
      <li>后端：Python + Flask，按蓝图（Blueprint）模块化划分</li>
      <li>统一接口返回格式：<code class="rounded bg-gray-100 px-1">{'{ code, message, data }'}</code></li>
    </ul>
  </section>
</template>

<script setup>
// 关于页面模板
</script>
