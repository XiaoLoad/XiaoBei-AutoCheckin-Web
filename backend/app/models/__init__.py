# 模型聚合层：统一暴露 db 与各模型，便于工厂 / 脚本引用
from app.extensions import db
from app.models.user import User
from app.models.token_blacklist import TokenBlacklist
from app.models.system_config import SystemConfig
from app.models.b_account import BAccount
from app.models.config_set import ConfigSet
from app.models.pools import PoolLocation, PoolCredential, PoolUa, PoolImage, ImageGroup
from app.models.schedule import Schedule
from app.models.sign_record import SignRecord

__all__ = [
    'db', 'User', 'TokenBlacklist', 'SystemConfig',
    'BAccount', 'ConfigSet',
    'PoolLocation', 'PoolCredential', 'PoolUa', 'PoolImage', 'ImageGroup',
    'Schedule', 'SignRecord',
]
