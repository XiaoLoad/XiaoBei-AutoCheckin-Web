# 系统用户模型：区分角色、bcrypt 哈希密码、账号启用状态
from datetime import datetime, timezone, timedelta

import bcrypt

from app.extensions import db

# 中国时区（UTC+8）。所有落库时间统一按中国本地时间存储，避免用 utcnow 导致
# 展示时间比真实时间早 8 小时（误显示为上午）。
CST = timezone(timedelta(hours=8))


def now_cst():
    """当前中国本地时间的朴素 datetime（不带时区信息，便于直接落库/格式化）。"""
    return datetime.now(CST).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    # bcrypt 哈希为 60 字符，预留长度
    password_hash = db.Column(db.String(120), nullable=False)
    # 角色：admin=管理员，user=普通用户
    role = db.Column(db.String(16), nullable=False, default='user', index=True)
    # 账号启用状态：禁用后禁止登录与所有接口访问
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    # 额度：quota 为总额度，used_quota 为已使用额度（如可创建的打卡任务/资源次数）
    quota = db.Column(db.Integer, nullable=False, default=100)
    used_quota = db.Column(db.Integer, nullable=False, default=0)
    # 密码版本号：每次密码变更（本人改密/管理员重置）自增。JWT 携带签发时的
    # pwd_ver，鉴权时与库值比对——不等即吊销，使改密后所有存量 token 立即失效。
    pwd_ver = db.Column(db.Integer, nullable=False, default=1, server_default='1')
    # 备注：管理员创建/编辑用户时填写，便于标识用户身份（如真实姓名、寝室号）
    remark = db.Column(db.String(128), nullable=False, default='', server_default='')
    created_at = db.Column(db.DateTime, default=now_cst)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        """使用 bcrypt 生成加盐哈希并存储"""
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password):
        """校验明文密码是否匹配哈希"""
        return bcrypt.checkpw(
            password.encode('utf-8'), self.password_hash.encode('utf-8')
        )

    def to_dict(self, used=None):
        """对外安全的用户基本信息（绝不返回密码哈希）。
        已用额度按产品定义恒等于平台账号数（现算）——存储 used_quota 计数器
        已被历史操作污染出漂移，不再对外展示。
        used 由列表查询一次性聚合后传入，避免逐用户 COUNT 的 N+1；单对象上下文省略时现算。"""
        if used is None:
            from app.models.b_account import BAccount
            used = BAccount.query.filter_by(user_id=self.id).count()
        return {
            'user_id': self.id,
            'username': self.username,
            'remark': self.remark or '',
            'role': self.role,
            'enabled': self.enabled,
            'quota': self.quota,
            'used_quota': used,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }

    def __repr__(self):
        return f'<User {self.username} role={self.role}>'
