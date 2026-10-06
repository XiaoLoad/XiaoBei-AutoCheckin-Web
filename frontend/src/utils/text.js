// 通用文本工具：HTML 转义与搜索命中高亮。
// 唯一出处——此前 UserManagementView 与 AccountTree 各持一份逐行相同的
// ESCAPE_MAP/escapeHtml/highlight，改动高亮样式要记得改两处（P3）。

const ESCAPE_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

export function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ESCAPE_MAP[c])
}

/**
 * 关键词命中高亮：先 HTML 转义再拼接 mark（原文不可信，直接 v-html 等于开注入口子）。
 * @param {string} text 原文
 * @param {string} kw 关键词（空串/未命中返回纯转义文本）
 * @param {string} markClass mark 元素的样式类
 */
export function highlightText(text, kw, markClass = 'rounded bg-amber/30 px-0.5 text-ink') {
  const raw = String(text ?? '')
  const q = String(kw ?? '').trim()
  if (!q) return escapeHtml(raw)
  const i = raw.toLowerCase().indexOf(q.toLowerCase())
  if (i < 0) return escapeHtml(raw)
  const hit = escapeHtml(raw.slice(i, i + q.length))
  return (
    `${escapeHtml(raw.slice(0, i))}` +
    `<mark class="${markClass}">${hit}</mark>` +
    `${escapeHtml(raw.slice(i + q.length))}`
  )
}
