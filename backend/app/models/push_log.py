# 推送日志：每次调度执行后各推送通道的真实发送结果流水（每通道一行）。
# 与 SignRecord 多对一（sign_record_id），随执行日志的删除/超期清理一并清理；
# 凭证「测试推送」不入库（结果即时回显给用户，无追溯价值）。
# 动机：曾发生 pushplus 单账号静默失败（李靖 9/1 早），错误只进控制台日志无法追溯，
# 故将通道、成败、原因原文、尝试次数、发送时刻持久化，任务日志详情直接可见。
from app.extensions import db
from app.models.user import now_cst


class PushLog(db.Model):
    __tablename__ = 'push_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('b_accounts.id'), index=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedules.id'), index=True)
    sign_record_id = db.Column(db.Integer, db.ForeignKey('sign_records.id'), index=True)
    channel = db.Column(db.String(16), nullable=False)              # pushplus | serverchan | email
    ok = db.Column(db.Boolean, nullable=False, default=False)       # 最终是否发送成功
    error = db.Column(db.String(500))                               # 失败原因原文（成功为空）
    attempts = db.Column(db.Integer, nullable=False, default=1)     # 实际尝试次数（含重试）
    template = db.Column(db.String(16))                             # html | txt | markdown
    created_at = db.Column(db.DateTime, default=now_cst, index=True)

    __table_args__ = (
        db.Index('ix_push_logs_record', 'sign_record_id'),
        db.Index('ix_push_logs_user_time', 'user_id', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'channel': self.channel,
            'ok': bool(self.ok),
            'error': self.error or '',
            'attempts': self.attempts,
            'template': self.template or '',
            'createdAt': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }
