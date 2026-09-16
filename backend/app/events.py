# 领域事件信号：基于 Flask 自带的 blinker，用于解耦跨模块副作用。
# 发布方无需感知订阅方，避免模块间硬连线。当前订阅方见 app/services/op_log.py
# （操作审计日志）；后续可继续挂刷新汇总、异地登录提醒等订阅者。
from blinker import Namespace

_signals = Namespace()

# 用户被创建 / 更新 / 状态变更 / 删除时发布，供关注的模块响应。
# update 额外带 before（变更前取值）与 password_changed，供审计还原 from→to
user_changed = _signals.signal('user-changed')
# 账号（B 平台）相关变更（预留，待 accounts 模块落地时使用）
account_changed = _signals.signal('account-changed')
# 登录尝试（成功与失败都会发布）：失败分支带 result='fail' 与 reason
auth_login = _signals.signal('auth-login')
# 修改登录密码成功后发布
auth_password_changed = _signals.signal('auth-password-changed')
# 退出登录（token 吊销）后发布，前端可据此统一清理
auth_logged_out = _signals.signal('auth-logged-out')
