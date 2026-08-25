# 资源池四表：位置 / 推送凭证 / UA 模板 / 图库元数据
# 删除策略（设计文档 §3.3）：被引用的资源返回 409 引用计数提示；未被引用物理删除
from app.extensions import db
from app.models.user import now_cst


class PoolLocation(db.Model):
    __tablename__ = 'pool_locations'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    address = db.Column(db.String(255))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=now_cst)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'address': self.address,
                'lat': self.lat, 'lng': self.lng, 'enabled': bool(self.enabled)}


class PoolCredential(db.Model):
    __tablename__ = 'pool_credentials'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    channel = db.Column(db.String(16), nullable=False)   # serverchan | pushplus | email
    name = db.Column(db.String(64), nullable=False)
    secret_enc = db.Column(db.Text, nullable=False)      # Fernet 密文（JSON 结构化凭证）
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=now_cst)


class PoolUa(db.Model):
    __tablename__ = 'pool_uas'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    remark = db.Column(db.String(255))
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=now_cst)

    def to_dict(self):
        return {'id': self.id, 'content': self.content, 'remark': self.remark,
                'enabled': bool(self.enabled)}


class PoolImage(db.Model):
    __tablename__ = 'pool_images'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    orig_name = db.Column(db.String(255))
    filename = db.Column(db.String(255))
    size = db.Column(db.Integer, default=0)
    mime = db.Column(db.String(64))
    status = db.Column(db.String(16), nullable=False, default='active')  # active | trash
    created_at = db.Column(db.DateTime, default=now_cst)
