# 领域事件信号：基于 Flask 自带的 blinker，用于解耦跨模块副作用。
# 当前仅定义信号；后续可注册订阅者（如刷新汇总、写审计日志），
# 发布方无需感知订阅方，避免模块间硬连线。
from blinker import Namespace

_signals = Namespace()

# 用户被创建 / 更新 / 删除 / 状态变更时发布，供关注的模块响应
user_changed = _signals.signal('user-changed')
# 账号（B 平台）相关变更（预留，待 accounts 模块落地时使用）
account_changed = _signals.signal('account-changed')
# 退出登录（token 吊销）后发布，前端可据此统一清理
auth_logged_out = _signals.signal('auth-logged-out')
