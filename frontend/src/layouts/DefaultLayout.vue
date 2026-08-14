<template>
  <div class="min-h-screen flex flex-col">
    <!-- 顶部导航 -->
    <header class="bg-white shadow">
      <nav class="max-w-5xl mx-auto px-4 h-14 flex items-center gap-6">
        <RouterLink to="/" class="font-bold text-brand">小北寝室打卡</RouterLink>
        <RouterLink to="/" class="text-gray-600 hover:text-brand">首页</RouterLink>
        <RouterLink to="/about" class="text-gray-600 hover:text-brand">关于</RouterLink>
        <div class="flex-1"></div>
        <RouterLink to="/login" class="text-sm font-medium text-brand hover:text-brand-dark">登录</RouterLink>
      </nav>
    </header>

    <!-- 主体内容 -->
    <main class="flex-1 max-w-5xl w-full mx-auto px-4 py-6">
      <slot />
    </main>

    <!-- 页脚 -->
    <footer class="bg-white border-t">
      <div class="max-w-5xl mx-auto px-4 h-12 flex items-center text-sm text-gray-400">
        小北寝室自动打卡项目 · Web 端基础框架
      </div>
    </footer>
  </div>
</template>

<script setup>
// 默认布局模板：导航 + 内容插槽 + 页脚
</script>
