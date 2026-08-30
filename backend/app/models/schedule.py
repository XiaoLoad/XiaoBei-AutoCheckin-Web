# 定时任务：账号 × 任务类型（dorm/activity 各一行，随账号自动生灭，无 POST/DELETE）
# mode=follow 时经 config_set_id 引用配置套（实时跟随）；standalone 时以 config_json 为任务自持完整配置
# （绑定/套用配置套即把配置快照复制进 config_json 并解绑，配置套此后仅为模板）
import json

from app.extensions import db
from app.models.user import now_cst


class Schedule(db.Model):
    __tablename__ = 'schedules'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('b_accounts.id'), nullable=False, index=True)
    task_type = db.Column(db.String(16), nullable=False)                 # dorm | activity
    mode = db.Column(db.String(16), nullable=False, default='follow')    # follow | custom | standalone
    custom_json = db.Column(db.Text)      # {"hour":8,"minute":0,"weekdays":[1..7],"randomDelayMax":5}
    config_set_id = db.Column(db.Integer, db.ForeignKey('config_sets.id'))
    # 字段级覆盖（follow 模式）：顶层配置键 → 替换值，如 {"time": {...}}；
    # 执行时与所绑配置套浅合并，未覆盖的键继续跟随配置套
    overrides_json = db.Column(db.Text)
    # 任务自持完整配置（standalone 模式权威来源）：时间/位置/备注/图片/推送/高级等全量字段。
    # 绑定或套用配置套时由后端把配置套解析结果快照复制到此列，并解绑 config_set_id（仅留作源自标签）。
    config_json = db.Column(db.Text)
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

    @property
    def overrides(self) -> dict:
        return json.loads(self.overrides_json) if self.overrides_json else {}

    @property
    def config(self) -> dict:
        """任务自持完整配置（standalone 权威来源）；为空时返回 {}。"""
        return json.loads(self.config_json) if self.config_json else {}

    def set_config(self, cfg: dict):
        self.config_json = json.dumps(cfg, ensure_ascii=False)

    @property
    def has_own_config(self) -> bool:
        """是否已持有自持配置（standalone 判定依据：config_json 非空即视为独立配置）。"""
        return bool(self.config_json)

    def to_dict(self):
        from app.models.b_account import BAccount
        from app.utils.schedule_utils import extract_jitter_minutes
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
            # 平台回填档案：真实姓名 / 学院 / 专业（登录账号 account 可能是手机号或身份证，不足以辨识身份）
            'studentName': profile.get('name') or '',
            'college': profile.get('college') or '',
            'major': profile.get('major') or '',
            'studentNo': profile.get('studentNo') or '',
            'className': profile.get('className') or '',
            'mode': self.mode,
            'configSetId': self.config_set_id,
            'config': self.config,
            'custom': self.custom,
            'overrides': self.overrides,
            'enabled': bool(self.enabled),
            # next_run_at 是未叠加随机延迟的基线时刻；实际执行在其后 randomDelayMax 分钟内随机漂移
            'nextRunAt': self.next_run_at.strftime('%Y-%m-%d %H:%M') if self.next_run_at else '',
            'nextRunJitterMin': extract_jitter_minutes(self) if self.enabled else 0,
            'lastRunAt': self.last_run_at.strftime('%Y-%m-%d %H:%M') if self.last_run_at else '',
            'lastStatus': self.last_status or 'never',
            'runCount': self.run_count,
        }
