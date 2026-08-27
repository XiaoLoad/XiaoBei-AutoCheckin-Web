# 定时任务：账号 × 任务类型（dorm/activity 各一行，随账号自动生灭，无 POST/DELETE）
# mode=follow 时经 config_set_id 引用配置套；custom 时用 custom_json 的时刻
import json

from app.extensions import db
from app.models.user import now_cst


class Schedule(db.Model):
    __tablename__ = 'schedules'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('b_accounts.id'), nullable=False, index=True)
    task_type = db.Column(db.String(16), nullable=False)                 # dorm | activity
    mode = db.Column(db.String(16), nullable=False, default='follow')    # follow | custom
    custom_json = db.Column(db.Text)      # {"hour":8,"minute":0,"weekdays":[1..7],"randomDelayMax":5}
    config_set_id = db.Column(db.Integer, db.ForeignKey('config_sets.id'))
    next_run_at = db.Column(db.DateTime, nullable=True)  # 下次执行时间缓存（调度器维护，便于前端展示）
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    last_run_at = db.Column(db.DateTime)
    last_status = db.Column(db.String(16))                               # success | fail | skip
    run_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=now_cst)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)

    __table_args__ = (
        db.UniqueConstraint('account_id', 'task_type', name='uq_schedules_account_task'),
    )

    @property
    def custom(self) -> dict:
        return json.loads(self.custom_json) if self.custom_json else {}

    def to_dict(self):
        from app.models.b_account import BAccount
        acc = db.session.get(BAccount, self.account_id)
        profile = acc.profile if acc else {}
        task_label = '寝室签到' if self.task_type == 'dorm' else '活动签到'
        return {
            'id': self.id,
            'userId': self.user_id,
            'accountId': self.account_id,
            'accountName': acc.account if acc else '',
            'accountEnabled': bool(acc.enabled) if acc else False,
            'taskType': self.task_type,
            'taskLabel': task_label,
            'platform': acc.platform if acc else '',
            'studentNo': profile.get('studentNo') or '',
            'className': profile.get('className') or '',
            'mode': self.mode,
            'configSetId': self.config_set_id,
            'custom': self.custom,
            'enabled': bool(self.enabled),
            'nextRunAt': self.next_run_at.strftime('%Y-%m-%d %H:%M') if self.next_run_at else '',
            'lastRunAt': self.last_run_at.strftime('%Y-%m-%d %H:%M') if self.last_run_at else '',
            'lastStatus': self.last_status or 'never',
            'runCount': self.run_count,
        }
