// 竞态请求守卫（唯一出处）：「seq 序号 + 仅采纳最新结果」在多个 store 里手写重复，
// 漏写一处就是一个竞态 bug（signRecords.toggleExpand 即是漏网实例，P3）。
// 用法：
//   const race = useRacedRequest()
//   async function load() {
//     const seq = race.begin()
//     try {
//       const res = await fetchSomething()
//       if (!race.isLatest(seq)) return   // 旧响应丢弃
//       ...
//     } finally {
//       if (race.isLatest(seq)) ...       // 只有最新请求有权收尾（关 loading 等）
//     }
//   }
//
// 守卫实例按调用点创建（各 store 的每条请求链各持一个），实例内序号自增；
// 不同实例互不干扰——竞态判断只在同一条请求链内部比较。
export function useRacedRequest() {
  let seq = 0
  return {
    /** 发起新请求：取号（自增并返回本次序号） */
    begin() {
      return ++seq
    },
    /** 该序号是否仍是本守卫内最新的一次请求 */
    isLatest(s) {
      return s === seq
    },
  }
}
