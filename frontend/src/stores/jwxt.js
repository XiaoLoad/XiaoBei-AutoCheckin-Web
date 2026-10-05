// 教务绑定领域状态（Pinia）：按 B 平台账号管理教务凭证绑定、课表概览与当日窗口。
// overview 以 accountId(字符串) 为键缓存；绑定/解绑/同步后仅刷新对应账号，避免全量重拉。
// 同步为**异步任务**：后端入队立即返回，此处轮询概览的 syncRunning 直到完成，
// 再按 account.status / lastError 归纳结果（教务网偶发秒级挂起，单次同步可达数十秒）。
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { toast } from '@/utils/toast'
import * as api from '@/api/jwxt'

const POLL_INTERVAL_MS = 2500
const POLL_MAX_TIMES = 60   // 2.5s × 60 = 150s 上限（覆盖最坏的挂起+重试组合）

export const useJwxtStore = defineStore('jwxt', () => {
  // accountId(String) → overview { bound, account, semester, courses, windows, timetableSyncedAt, syncRunning }
  const overviews = ref({})
  const syncing = ref({})     // accountId → true（前端视角的同步进行中：已提交且未出结果）
  const loading = ref({})
  const polling = ref({})     // accountId → true（waitSyncDone 轮询进行中，防重入）
  // 轮询代数（T9.2）：waitSyncDone 是 150s 的长循环，旧实例无法被取消——
  // 每次进入时自增代数，循环内发现代数已变（新一轮 bind/sync 开始）立即退出，
  // 杜绝「绑 A → 秒解绑再绑 B，A 的旧轮询把 B 的结果覆盖成 A 的概览」的串扰。
  let pollEpoch = 0

  function keyOf(id) {
    return String(id)
  }

  async function load(accountId, opts = {}) {
    const key = keyOf(accountId)
    if (!opts.force && loading.value[key]) return overviews.value[key]
    loading.value = { ...loading.value, [key]: true }
    try {
      const data = await api.fetchJwxtOverview(accountId)
      overviews.value = { ...overviews.value, [key]: data }
      return data
    } catch (e) {
      // 静默失败（接口 silent）：未绑定/未同步属常态，不弹全局 toast。
      // [T9.2] 返回 null 而非伪造的空对象：waitSyncDone 据此区分「同步结束」与
      // 「网络抖动」——误判结束会让按钮 spinner 提前消失、结果被报成失败。
      return null
    } finally {
      loading.value = { ...loading.value, [key]: false }
    }
  }

  // 批量预热（账号任务配置页挂载时按账号树拉一遍，供树徽标展示）
  async function loadMany(accountIds) {
    await Promise.all((accountIds || []).map((id) => load(id)))
  }

  // 轮询直到后台同步结束（syncRunning 转 false）或超时。
  // 返回最终 overview；期间 syncing 状态保持 true 驱动按钮 spinner。
  // [T9.2] 入口防重入（同账号已有轮询直接复用）+ 代数守卫（新一轮 bind/sync
  // 让旧轮询立即失效退出）；网络抖动轮次（load 返回 null）不视为同步结束，继续等。
  async function waitSyncDone(accountId) {
    const key = keyOf(accountId)
    if (polling.value[key]) {
      // 已有同账号轮询在跑：等它出结果即可，不再叠一层空转
      while (polling.value[key]) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS))
      }
      return load(accountId, { force: true })
    }
    polling.value = { ...polling.value, [key]: true }
    const epoch = ++pollEpoch
    try {
      for (let i = 0; i < POLL_MAX_TIMES; i++) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS))
        if (epoch !== pollEpoch) return null  // 新一轮 bind/sync 已接管，本轮作废
        const data = await load(accountId, { force: true })
        if (data?.syncRunning === false) return data
      }
      return load(accountId, { force: true })
    } finally {
      polling.value = { ...polling.value, [key]: false }
    }
  }

  function reportResult(accountId, overview, action) {
    const acc = overview?.account
    if (overview?.bound && acc && acc.status === 'ok' && !acc.lastError) {
      toast(action === 'bind' ? '绑定成功，课表已同步' : '课表已同步', 'success')
      return true
    }
    toast(acc?.lastError || '同步未完成，请稍后重试', 'error')
    return false
  }

  async function bind(accountId, { studentNo, password }) {
    const key = keyOf(accountId)
    syncing.value = { ...syncing.value, [key]: true }
    try {
      await api.bindJwxt(accountId, { studentNo, password })
      const final = await waitSyncDone(accountId)
      return reportResult(accountId, final, 'bind')
    } catch (e) {
      // 错误提示由请求拦截器统一弹出（含"账号或密码错误，未绑定"），此处不再叠加
      load(accountId, { force: true })
      return false
    } finally {
      syncing.value = { ...syncing.value, [key]: false }
    }
  }

  async function sync(accountId) {
    const key = keyOf(accountId)
    syncing.value = { ...syncing.value, [key]: true }
    try {
      await api.syncJwxt(accountId)
      const final = await waitSyncDone(accountId)
      return reportResult(accountId, final, 'sync')
    } catch (e) {
      load(accountId, { force: true })
      return false
    } finally {
      syncing.value = { ...syncing.value, [key]: false }
    }
  }

  async function unbind(accountId) {
    const key = keyOf(accountId)
    syncing.value = { ...syncing.value, [key]: true }
    try {
      await api.unbindJwxt(accountId)
      await load(accountId, { force: true })
      toast('已解绑教务账号', 'success')
      return true
    } catch (e) {
      return false
    } finally {
      syncing.value = { ...syncing.value, [key]: false }
    }
  }

  function overviewOf(accountId) {
    return overviews.value[keyOf(accountId)] || null
  }
  function isBound(accountId) {
    return !!overviewOf(accountId)?.bound
  }

  return { overviews, syncing, loading, polling, load, loadMany, bind, sync, unbind, overviewOf, isBound }
})
