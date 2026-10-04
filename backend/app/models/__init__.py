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
from app.models.push_log import PushLog
from app.models.op_log import OpAnomalyAck, OpLog
from app.models.login_failure import LoginFailure
from app.models.jwxt import JwAccount, JwSemester, JwTimetable, ActivityWindow
from app.models.group_push import (
    PushGroup, PushGroupMember, PushGroupDigestLog, PushGroupDigestPending,
)

__all__ = [
    'db', 'User', 'TokenBlacklist', 'SystemConfig',
    'BAccount', 'ConfigSet',
    'PoolLocation', 'PoolCredential', 'PoolUa', 'PoolImage', 'ImageGroup',
    'Schedule', 'SignRecord', 'PushLog', 'OpLog', 'OpAnomalyAck', 'LoginFailure',
    'JwAccount', 'JwSemester', 'JwTimetable', 'ActivityWindow',
    'PushGroup', 'PushGroupMember', 'PushGroupDigestLog', 'PushGroupDigestPending',
]
