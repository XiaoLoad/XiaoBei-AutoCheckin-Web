// 前后端契约类型定义（JSDoc typedef）。
// 与后端 app/schemas/* 及接口返回结构保持一致，作为前端消费数据的权威形状参考，
// 避免 mock 数据与现实实现漂移。改动接口前请先同步此处与后端 schemas。

/**
 * 账号个人信息（登录后由平台回填，用户不可手改）
 * @typedef {Object} AccountProfile
 * @property {string} name       姓名
 * @property {string} college    学院
 * @property {string} major      专业
 * @property {string} className  班级
 * @property {string} studentNo  学号
 */

/** 上一次签到状态 */
/** @typedef {('success'|'fail'|'skip'|'never')} SignStatus */

/**
 * B 平台账号（账号管理页核心数据对象）
 * @typedef {Object} Account
 * @property {number} id
 * @property {string} account       B 平台账号标识
 * @property {string} platform      平台名称
 * @property {('dorm'|'activity'|'general')} type   签到类型
 * @property {boolean} enabled       是否启用
 * @property {AccountProfile} profile       个人信息（平台回填）
 * @property {{ time: string, ok?: boolean, status?: SignStatus }} lastSignIn  上一次签到
 * @property {string} createdAt      创建时间
 */

/**
 * 用户列表项（用户管理页）
 * @typedef {Object} UserListItem
 * @property {number} user_id
 * @property {string} username
 * @property {('admin'|'user')} role
 * @property {boolean} enabled
 * @property {number} quota          额度上限
 * @property {number} used_quota     已用额度
 * @property {string} created_at     创建时间
 */

/**
 * 用户列表响应
 * @typedef {Object} UserListResult
 * @property {UserListItem[]} items
 * @property {number} total
 * @property {number} page
 * @property {number} page_size
 * @property {{ total_users:number, enabled:number, disabled:number, total_quota:number, used_quota:number }} summary
 */
