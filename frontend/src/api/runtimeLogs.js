// 运行日志（服务端 app.log 只读尾部）接口：对应后端 /api/admin/runtime-logs（仅管理员）。
// request 已统一给 URL 加 /api 前缀，故此处只写相对路径。
import request from '@/api/request'

// params = { tail: 行数上限, q: 关键字, rotated: 是否并入轮转文件 }
export async function fetchRuntimeLogs(params = {}) {
  const data = await request({ url: '/admin/runtime-logs', method: 'get', params })
  return {
    items: (data.items || []).map((it) => ({
      file: it.file || 'app.log',
      line: it.line || '',
    })),
    tail: data.tail || 300,
    q: data.q || '',
    rotated: !!data.rotated,
  }
}

// 导出当前筛选的日志为 txt：走 axios blob（复用统一鉴权与 401 处理；
// blob 响应被 request.js 拦截器原样放行为 Blob 本体，headers 挂在 __headers__）。
// 文件名由前端按筛选状态生成（后端不再回传 disposition），带关键字与时间戳防覆盖。
// 命中行数取后端 X-Log-Lines 响应头（导出大文件时不为显示行数读整 blob 进内存）。
export async function exportRuntimeLogs({ q = '', rotated = false } = {}) {
  const blob = await request({
    url: '/admin/runtime-logs',
    method: 'get',
    params: { tail: 2000, q, rotated, format: 'txt' },
    responseType: 'blob',
    timeout: 30000,
    // 导出是显式动作，失败由调用方在按钮处提示，不走全局 toast 双报
    silent: true,
  })
  const stamp = new Date().toISOString().slice(0, 19).replace(/[T:]/g, '').replace(/-/g, '')
  const tag = (q || '').replace(/[^\w\u4e00-\u9fff]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 32) || 'all'
  const rotatedTag = rotated ? '_rotated' : ''
  const lines = parseInt(blob.__headers__?.get?.('x-log-lines') || '', 10)
  return { blob, filename: `runtime_logs_${tag}_${stamp}${rotatedTag}.txt`, count: Number.isNaN(lines) ? 0 : lines }
}
