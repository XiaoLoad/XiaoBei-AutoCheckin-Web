<template>
  <!--
    空白布局（登录等独立页）：仅做全屏容器，并自行持有唯一的 RouterView 出口，
    路由组件由此渲染。与 DashboardLayout 保持一致（各自持有 RouterView），
    避免把 RouterView 当插槽传入复用布局导致路由不切换。
  -->
  <div class="min-h-screen w-full">
    <RouterView />
  </div>
</template>

<script setup>
import { RouterView } from 'vue-router'
</script>
