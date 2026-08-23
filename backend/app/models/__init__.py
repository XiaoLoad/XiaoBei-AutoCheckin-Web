# 模型聚合层：统一暴露 db 与各模型，便于工厂 / 脚本引用
from app.extensions import db
from app.models.user import User
from app.models.token_blacklist import TokenBlacklist
from app.models.system_config import SystemConfig

__all__ = ['db', 'User', 'TokenBlacklist', 'SystemConfig']
