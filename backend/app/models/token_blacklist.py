# 令牌黑名单：用于服务端吊销已签发的 JWT（实现"退出登录后立即失效"）
# 即使 JWT 本身无状态、调用方已清除本地 token，被吊销的 token 仍会被服务端拦截，
# 从而保证退出登录后无法继续访问受保护资源。
from datetime import datetime

from app.extensions import db


class TokenBlacklist(db.Model):
    __tablename__ = 'token_blacklist'

    # JWT 的 jti（唯一标识），作为主键
    jti = db.Column(db.String(64), primary_key=True)
    # 原 token 的过期时间，用于定期清理过期记录，避免表无限增长
    exp = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<TokenBlacklist jti={self.jti}>'
