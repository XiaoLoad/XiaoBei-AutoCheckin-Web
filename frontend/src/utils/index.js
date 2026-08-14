// 通用工具函数集合
// 可按需在此追加：日期格式化、深拷贝、防抖节流等

// 日期格式化：YYYY-MM-DD HH:mm:ss
export function formatDateTime(date = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  )
}

// 深拷贝（简易版）
export function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj))
}
