# 登录失败计数：防暴力破解的持久化防线（账号×IP / 账号全局 / IP 全局三维度）
# 不建外键——不存在的用户名同样要计数，否则「账号不存在」分支就绕过了计数逻辑。
from datetime import datetime

from app.extensions import db


class LoginFailure(db.Model):
    __tablename__ = 'login_failures'

    # 计数维度键：'u:{username}:ip:{ip}' / 'u:{username}' / 'ip:{ip}'
    key = db.Column(db.String(160), primary_key=True)
    # 窗口内失败次数（窗口以 last_fail_at 滑动判定）
    fail_count = db.Column(db.Integer, nullable=False, default=0)
    # 非空表示锁定中：此时拒绝一切该维度命中的登录尝试
    locked_until = db.Column(db.DateTime, nullable=True)
    # 最后一次失败时间：滑动窗口起点，兼作过期清理依据
    last_fail_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<LoginFailure {self.key} count={self.fail_count}>'
