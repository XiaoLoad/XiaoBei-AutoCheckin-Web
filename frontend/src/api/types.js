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

/**
 * 签到记录（第三方数据，按单个平台账号查询）
 * @typedef {Object} SignRecord
 * @property {number} id
 * @property {number} accountId      所属 B 平台账号 id
 * @property {string} taskName       任务名称
 * @property {('dorm'|'activity')} type   签到类型：寝室签到 / 活动签到
 * @property {string} date           日期 YYYY-MM-DD
 * @property {string} time           时间 HH:mm
 * @property {string} initiator      发起人（漏签时为「—」）
 * @property {('signed'|'unsigned')} status   状态：已签到 / 未签到（漏签）
 */
