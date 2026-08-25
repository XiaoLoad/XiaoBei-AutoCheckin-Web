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
