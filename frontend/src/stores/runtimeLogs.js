// 运行日志领域状态（Pinia）：服务端 app.log 只读尾部的取数与筛选。
// 排障场景是「反复换关键字看原文」，不是分页浏览——故无分页，
// tail 一次拉够，关键字过滤由后端在文件内容上做（前端只呈现）。
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { exportRuntimeLogs, fetchRuntimeLogs } from '@/api/runtimeLogs'

export const useRuntimeLogsStore = defineStore('runtimeLogs', () => {
  const items = ref([])
  const loading = ref(false)
  const refreshing = ref(false)
  const loaded = ref(false)
  const error = ref('')

  // 筛选状态：tail 行数上限 / q 关键字 / rotated 并入轮转文件
  const tail = ref(300)
  const keyword = ref('')
  const rotated = ref(false)

  async function load({ silent = false } = {}) {
    if (silent) refreshing.value = true
    else loading.value = true
    error.value = ''
    try {
      const data = await fetchRuntimeLogs({
        tail: tail.value,
        q: keyword.value,
        rotated: rotated.value,
      })
      items.value = data.items
      loaded.value = true
    } catch (e) {
      error.value = e?.message || '运行日志加载失败'
      // 静默刷新失败保留旧数据（排障页面闪空比旧一秒更糟）
    } finally {
      loading.value = false
      refreshing.value = false
    }
  }

  function setFilters(patch) {
    const next = { ...{ tail: tail.value, keyword: keyword.value, rotated: rotated.value }, ...patch }
    const changed =
      next.tail !== tail.value || next.keyword !== keyword.value || next.rotated !== rotated.value
    tail.value = next.tail
    keyword.value = next.keyword
    rotated.value = next.rotated
    if (changed) return load()
    return Promise.resolve()
  }

  function reset() {
    items.value = []
    loaded.value = false
    error.value = ''
    tail.value = 300
    keyword.value = ''
    rotated.value = false
  }

  // 导出当前筛选为 txt 附件：导出的是「当前筛选命中的原文」而非界面投影，
  // 行数上限用接口顶格 2000（界面 tail 只是显示密度，导出应尽量拿全）。
  // 返回 { filename, count }；count=0 时调用方提示无可导内容，不生成空文件。
  const exporting = ref(false)
  async function exportLogs() {
    if (exporting.value) return null
    exporting.value = true
    try {
      const { blob, filename } = await exportRuntimeLogs({
        q: keyword.value,
        rotated: rotated.value,
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
      const count = blob.size ? blob.text().then((t) => t.split('\n').filter(Boolean).length) : 0
      return { filename, count: await count }
    } finally {
      exporting.value = false
    }
  }

  return {
    items, loading, refreshing, loaded, error,
    tail, keyword, rotated, exporting,
    load, setFilters, reset, exportLogs,
  }
})
