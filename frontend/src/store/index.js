// 状态管理：使用 Pinia 创建根 store
// 各业务模块的状态建议拆分到 store/modules 下，再在此处统一聚合
import { createPinia } from 'pinia'

const pinia = createPinia()

export default pinia
