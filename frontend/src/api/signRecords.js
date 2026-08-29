// 签到记录接口（接真实后端 /api/accounts）：B 平台历史签到数据经后端代理读取，
// 前端不持有任何 B 平台凭据 / token。后端 accounts 蓝图契约见 backend/app/routes/accounts.py。
//
//   GET /api/accounts/:id/sign-records?type=dorm|activity&page=&page_size=
//       合并寝/活历史任务，后端排序分页；返回 { items, total, page, page_size }
//   GET /api/accounts/:id/sign-records/:taskId/detail?kind=know|sign
//       任务地理围栏 + 签到记录列表；返回 { geoFence, logs }
//   图片：B 平台图片接口为公开静态资源、<img> 不受 CORS 约束，日志内已直接回填
//        imageUrl（B 平台直链），前端 <img :src> 直连即可，无需后端代理、也不带 token
import request from '@/api/request'
import { fetchAccounts } from '@/api/accounts'

const DEFAULT_PAGE_SIZE = 10

// 拉取指定账号的历史签到任务（分页 + 类型筛选，全部在后端完成）
export async function fetchSignRecords(accountId, { type = 'all', page = 1, pageSize = DEFAULT_PAGE_SIZE } = {}) {
  if (!accountId) return { items: [], total: 0, page: 1, page_size: pageSize }
  const data = await request({
    url: `/accounts/${accountId}/sign-records`,
    method: 'get',
    params: { type, page, page_size: pageSize },
  })
  return {
    items: data.items || [],
    total: data.total || 0,
    page: data.page || page,
    page_size: data.page_size || pageSize,
  }
}

// 拉取单个任务的地理围栏 + 签到记录（点击展开时懒加载）
export async function fetchTaskDetail(accountId, taskId, kind = 'know') {
  if (!accountId || !taskId) return { geoFence: [], logs: [] }
  const data = await request({
    url: `/accounts/${accountId}/sign-records/${taskId}/detail`,
    method: 'get',
    params: { kind },
  })
  return { geoFence: data.geoFence || [], logs: data.logs || [] }
}

// 暴露给 store 用于默认选中第一个账号
export { fetchAccounts }
