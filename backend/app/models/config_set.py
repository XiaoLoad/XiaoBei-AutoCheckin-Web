# 签到配置套：用户级资产；任务实例通过 schedules.config_set_id 引用（多对多桥梁）
# config_json 形状契约见设计文档 §3.2（time/remarks/image/push/uaId）
# task_type：适用签到类型（dorm 寝室 / activity 活动），创建后锁定不可改——
# 防止寝室套被套到活动任务产生语义错配（活动块对寝室任务是不可消费的死配置）
import json

from app.extensions import db
from app.models.user import now_cst


class ConfigSet(db.Model):
    __tablename__ = 'config_sets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False, default='默认配置')
    is_default = db.Column(db.Boolean, nullable=False, default=False)   # 每用户每类型一条，应用层保证唯一
    task_type = db.Column(db.String(16), nullable=False, default='dorm')  # dorm | activity
    location_id = db.Column(db.Integer, db.ForeignKey('pool_locations.id'))
    config_json = db.Column(db.Text)     # JSON 字符串
    created_at = db.Column(db.DateTime, default=now_cst)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)

    @property
    def config(self) -> dict:
        return json.loads(self.config_json) if self.config_json else {}

    def set_config(self, cfg: dict):
        self.config_json = json.dumps(cfg, ensure_ascii=False)

    @classmethod
    def enforce_single_default(cls, user_id, keep_id, task_type=None):
        """保证某用户仅一条 is_default：把其余配置套置为 False。
        task_type 给定时按类型隔离（寝室/活动各留一条默认套，互不挤占）。"""
        q = cls.query.filter_by(user_id=user_id).filter(cls.id != keep_id)
        if task_type:
            q = q.filter(cls.task_type == task_type)
        q.update({'is_default': False})

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'isDefault': bool(self.is_default),
            'taskType': self.task_type or 'dorm',
            'locationId': self.location_id, 'config': self.config,
            'updatedAt': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
        }
