# 系统配置模型：键值表存储运行期可调的系统参数（注册开关/默认额度/会话时长等）。
# 设计要点：
#   - 未落库的键自动回退到 DEFAULTS 注册表中的默认值，无需种子数据即可工作；
#   - 管理员在设置页修改后即时生效（会话时长对下一次签发的 token 生效）。
from app.extensions import db
from app.models.user import now_cst


class SystemConfig(db.Model):
    """系统配置键值对：仅管理员通过设置页读写。"""

    __tablename__ = 'system_configs'

    key = db.Column(db.String(64), primary_key=True)
    # 统一以字符串落库，读取时按 DEFAULTS 注册的类型还原，避免类型漂移
    value = db.Column(db.String(255), nullable=False, default='')
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)
    updated_by = db.Column(db.String(64))  # 最后操作人用户名（审计线索）

    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
            'updated_by': self.updated_by or '',
        }


# 默认配置注册表：type 决定落库字符串的解析方式；
# value=None 表示无固定默认值（如 session_hours 回退到 .env 的 JWT_EXPIRES_HOURS）。
DEFAULTS = {
    'registration_enabled': {
        'value': True,
        'type': 'bool',
        'label': '开放自主注册',
        # 当前版本尚无自助注册接口（注册页为管理员开通引导），该开关为前瞻配置，
        # 已通过 GET /api/settings/public 暴露，注册接口落地后直接消费
        'desc': '是否允许访客自助创建账号；当前版本由管理员统一开通，注册接口上线后本开关即时管控',
    },
    'default_quota': {
        'value': 100,
        'type': 'int',
        'min': 1,
        'max': 999999,
        'label': '新用户默认额度',
        'desc': '新建用户未显式指定额度时的初始值',
    },
    'session_hours': {
        'value': None,
        'type': 'int',
        'min': 1,
        'max': 720,
        'label': '登录会话有效期（小时）',
        'desc': '签发登录凭证的有效时长，修改后对下一次登录生效',
    },
    'password_min_length': {
        'value': 6,
        'type': 'int',
        'min': 4,
        'max': 64,
        'label': '密码最小长度',
        'desc': '设置密码与新建用户时校验的密码下限',
    },
    'sign_log_retention_days': {
        'value': 180,
        'type': 'int',
        'min': 1,
        'max': 3650,
        'label': '签到日志保留天数',
        'desc': '超过该天数的执行日志由系统自动清理；用户仍可在日志页手动删除自己的记录',
    },
}


def _coerce(key, raw):
    """按注册表的类型把字符串还原为 bool/int；解析失败回退默认值"""
    spec = DEFAULTS.get(key)
    if not spec:
        return raw
    if spec['type'] == 'bool':
        return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')
    try:
        return int(raw)
    except (TypeError, ValueError):
        return spec['value']


def get_setting(key):
    """
    读取单个配置项：优先取数据库行，其次注册表默认值。
    session_hours 这类 value=None 的键最终回退到应用配置，由调用方兜底。
    数据库不可用时静默降级为默认值，避免配置读取阻断业务接口。
    """
    spec = DEFAULTS.get(key)
    if not spec:
        raise KeyError(f'未知系统配置项: {key}')
    try:
        row = SystemConfig.query.filter_by(key=key).first()
        if row is not None and row.value != '':
            return _coerce(key, row.value)
    except Exception:
        pass
    return spec['value']


def set_setting(key, value, operator=''):
    """写入单个配置项（upsert）；value 统一转字符串落库"""
    spec = DEFAULTS.get(key)
    if not spec:
        raise KeyError(f'未知系统配置项: {key}')
    stored = ('true' if value else 'false') if spec['type'] == 'bool' else str(value)
    row = SystemConfig.query.filter_by(key=key).first()
    if row is None:
        row = SystemConfig(key=key, value=stored, updated_by=operator)
        db.session.add(row)
    else:
        row.value = stored
        row.updated_by = operator
        db.session.add(row)
