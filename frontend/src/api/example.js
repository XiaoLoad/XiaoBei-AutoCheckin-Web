// 示例接口模块：演示如何按业务模块组织 API 调用
import request from './request'

// 获取示例列表
export function getExampleList(params) {
  return request({ url: '/example', method: 'get', params })
}

// 获取单条示例
export function getExampleDetail(id) {
  return request({ url: `/example/${id}`, method: 'get' })
}

// 创建示例
export function createExample(data) {
  return request({ url: '/example', method: 'post', data })
}
