# 签到配置套：用户级资产；任务实例通过 schedules.config_set_id 引用（多对多桥梁）
# config_json 形状契约见设计文档 §3.2（time/remarks/image/push/uaId）
import json

from app.extensions import db
from app.models.user import now_cst


class ConfigSet(db.Model):
    __tablename__ = 'config_sets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False, default='默认配置')
    is_default = db.Column(db.Boolean, nullable=False, default=False)   # 每用户一条，应用层保证唯一
    location_id = db.Column(db.Integer, db.ForeignKey('pool_locations.id'))
    config_json = db.Column(db.Text)     # JSON 字符串
    created_at = db.Column(db.DateTime, default=now_cst)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)

    @property
    def config(self) -> dict:
        return json.loads(self.config_json) if self.config_json else {}

    def set_config(self, cfg: dict):
        self.config_json = json.dumps(cfg, ensure_ascii=False)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'isDefault': bool(self.is_default),
            'locationId': self.location_id, 'config': self.config,
            'updatedAt': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
        }
