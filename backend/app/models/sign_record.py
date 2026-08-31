# 签到记录：调度执行结果流水（success/fail/skip），仪表盘与记录页的数据源
import json

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
    # 执行时配置快照（JSON 字符串）：落库瞬间抓取 resolved 配置的可读渲染，作为历史切片。
    # 存量记录为 NULL —— 详情接口据此返回 hasSnapshot=false，前端显示「无配置快照」。
    config_snapshot = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now_cst)

    __table_args__ = (
        db.Index('ix_records_user_date', 'user_id', 'sign_date'),
        db.Index('ix_records_account_date', 'account_id', 'sign_date'),
    )

    def set_config_snapshot(self, cfg):
        """写入执行时配置快照（dict→JSON）；None 表示无快照（如执行前配置缺失）。"""
        self.config_snapshot = json.dumps(cfg, ensure_ascii=False) if cfg is not None else None

    def get_config_snapshot(self):
        """读出配置快照；非法或为空返回 None。"""
        if not self.config_snapshot:
            return None
        try:
            return json.loads(self.config_snapshot)
        except (ValueError, TypeError):
            return None
