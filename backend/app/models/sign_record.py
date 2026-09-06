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
    # 实际提交参数快照（JSON 字符串）：落库本次尝试提交的真实载荷（含 10m 抖动后坐标/
    # 实际单条备注/平台任务 ID/图片策略与回退提示等），供详情回显「提交参数」。
    # 未进入提交阶段（如被跳过或提交前已失败）则为 NULL。
    submit_params = db.Column(db.Text)
    # 课程溯源（活动签到课表驱动调度）：窗口轮询命中活动时记录所属课程名；
    # 寝室签到与固定策略活动为 NULL
    course_name = db.Column(db.String(64))
    # 索引：保留策略清理 job 按 created_at 做范围 DELETE，无索引时退化为全表扫描
    created_at = db.Column(db.DateTime, default=now_cst, index=True)

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

    def set_submit_params(self, cfg):
        """写入本次提交参数快照（dict→JSON）；None 表示未进入提交阶段（如被跳过）。"""
        self.submit_params = json.dumps(cfg, ensure_ascii=False) if cfg is not None else None

    def get_submit_params(self):
        """读出提交参数快照；非法或为空返回 None。"""
        if not self.submit_params:
            return None
        try:
            return json.loads(self.submit_params)
        except (ValueError, TypeError):
            return None
