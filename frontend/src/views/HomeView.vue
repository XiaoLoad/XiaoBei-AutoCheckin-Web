<template>
  <section>
    <h1 class="text-2xl font-bold text-gray-900">首页</h1>
    <p class="mt-2 text-gray-600">
      这是前后端分离基础框架的首页模板，下方演示了前端通过 axios 调用后端示例接口。
    </p>

    <div class="mt-6 flex items-center gap-3">
      <button
        class="rounded-md bg-brand px-4 py-2 text-white hover:bg-brand-dark disabled:opacity-50"
        :disabled="loading"
        @click="loadList"
      >
        {{ loading ? '加载中…' : '调用示例接口' }}
      </button>
      <span v-if="error" class="text-sm text-red-500">{{ error }}</span>
    </div>

    <div v-if="list.length" class="mt-6 grid gap-3 sm:grid-cols-2">
      <ExampleCard
        v-for="item in list"
        :key="item.id"
        :title="`#${item.id} ${item.name}`"
      >
        来自后端 /api/example 接口的示例数据
      </ExampleCard>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getExampleList } from '@/api/example'
import ExampleCard from '@/components/ExampleCard.vue'

const list = ref([])
const loading = ref(false)
const error = ref('')

async function loadList() {
  loading.value = true
  error.value = ''
  try {
    list.value = await getExampleList({ keyword: '' })
  } catch (e) {
    error.value = e.message || '请求失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadList)
</script>
