<template>
  <div class="space-y-6">
    <!--
      ============================================================
      首页仪表盘分发器（A 平台）
      [权限判断] 根据当前登录角色分发到两套页面：
        - 管理员  → AdminDashboard（全站视角，含汇总/图表/额度预警/调度器）
        - 普通用户 → UserDashboard（本人视角，受额度约束）
      真实项目中 role 由后端按 token 返回，路由守卫需拦截越权访问。
      ============================================================
    -->
    <component :is="dashboard" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import AdminDashboard from '@/views/AdminDashboard.vue'
import UserDashboard from '@/views/UserDashboard.vue'

// 当前角色（mock；真实由后端按 token 返回，例：useAuth().role）
const role = '管理员' // 切换为 '普通用户' 即渲染普通用户仪表盘

const dashboard = computed(() => (role === '管理员' ? AdminDashboard : UserDashboard))
</script>
