<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between gap-2">
      <p class="text-xs text-ink-muted">
        系统级 UA 模板（机型默认值），由管理员维护；普通用户在「高级设置」中下拉选择，亦可自定义填写。
      </p>
      <button
        v-if="isAdmin"
        type="button"
        class="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-dark disabled:opacity-50"
        :disabled="editing"
        @click="openAdd"
      >
        <Icon name="plus" :size="15" />添加模板
      </button>
    </div>

    <!-- 内联表单 -->
    <div v-if="editing" class="rounded-xl border border-brand/20 bg-brand/5 p-3">
      <input
        v-model="form.name"
        class="mb-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
        placeholder="模板名称（如 iPhone 15）"
      />
      <textarea
        v-model="form.ua"
        rows="3"
        class="w-full resize-y rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/10"
        placeholder="User-Agent 字符串"
      />
      <div class="mt-2 flex justify-end gap-2">
        <button class="rounded-lg border border-ink/10 px-3 py-1.5 text-sm text-ink-soft hover:bg-cloud" @click="editing = null">取消</button>
        <button
          class="rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
          :disabled="!form.name || !form.ua"
          @click="save"
        >
          保存
        </button>
      </div>
    </div>

    <!-- 列表 -->
    <div v-if="store.uaTemplates.length === 0" class="py-8 text-center text-sm text-ink-muted">暂无模板</div>
    <div v-else class="grid grid-cols-1 gap-2 sm:grid-cols-2">
      <div v-for="u in store.uaTemplates" :key="u.id" class="rounded-xl border border-ink/10 bg-white p-3">
        <div class="mb-1 flex items-center justify-between gap-2">
          <p class="text-sm font-medium text-ink">{{ u.name }}</p>
          <div v-if="isAdmin" class="flex shrink-0 gap-3">
            <button class="text-xs text-brand hover:underline" @click="openEdit(u)">编辑</button>
            <button class="text-xs text-danger hover:underline" @click="del(u)">删除</button>
          </div>
        </div>
        <p class="break-all text-xs text-ink-muted">{{ u.ua }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import Icon from '@/components/Icon.vue'
import { useSignConfigStore } from '@/stores/signConfig'
import { useAuthStore } from '@/store/modules/auth'

const store = useSignConfigStore()
const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

const editing = ref(false)
const form = reactive({ id: '', name: '', ua: '' })

function openAdd() {
  form.id = ''
  form.name = ''
  form.ua = ''
  editing.value = true
}
function openEdit(u) {
  form.id = u.id
  form.name = u.name
  form.ua = u.ua
  editing.value = true
}
async function save() {
  await store.saveUaTemplate({ id: form.id || undefined, name: form.name, ua: form.ua })
  editing.value = false
}
function del(u) {
  store.deleteUaTemplate(u.id)
}
</script>
