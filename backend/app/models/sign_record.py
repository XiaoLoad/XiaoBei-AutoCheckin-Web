# 签到记录：调度执行结果流水（success/fail/skip），仪表盘与记录页的数据源
from app.extensions import db
from app.models.user import now_cst


class SignRecord(db.Model):
    __tablename__ = 'sign_records'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('b_accounts.id'), nullable=False, index=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedules.id'))
    task_name = db.Column(db.String(64))
    task_type = db.Column(db.String(16))
    sign_date = db.Column(db.Date, nullable=False, index=True)
    signed_at = db.Column(db.DateTime)
    status = db.Column(db.String(16), nullable=False)                    # success | fail | skip
    fail_reason = db.Column(db.String(255))
    initiator = db.Column(db.String(16), nullable=False, default='system')  # system | manual
    created_at = db.Column(db.DateTime, default=now_cst)

    __table_args__ = (
        db.Index('ix_records_user_date', 'user_id', 'sign_date'),
        db.Index('ix_records_account_date', 'account_id', 'sign_date'),
    )
