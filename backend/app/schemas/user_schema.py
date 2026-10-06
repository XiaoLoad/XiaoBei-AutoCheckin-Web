# 用户相关入参校验层（零依赖，可作为前后端契约的权威定义）。
# 设计目标：把散落在路由里的字段校验集中到此，统一错误信息与错误码；
# 未来若引入 marshmallow / pydantic，可平滑替换为对应 Schema，接口形态不变。
from app.models.system_config import get_setting
from app.utils.validators import (PASSWORD_MAX_BYTES, password_too_long,
                                  validate_role, validate_username)

# 兜底下限：系统配置不可用时仍保证基本安全（正常取值来自设置页的 password_min_length）
FALLBACK_PASSWORD_MIN = 6


def _password_min():
    """密码最小长度：跟随系统设置，读取异常时回退固定下限"""
    try:
        return int(get_setting('password_min_length') or FALLBACK_PASSWORD_MIN)
    except Exception:
        return FALLBACK_PASSWORD_MIN


def load_create(payload):
    """校验『新增用户』入参。返回 (ok, data, message, code)。"""
    payload = payload or {}
    ok, username, msg, code = validate_username(payload.get('username'))
    if not ok:
        return False, None, msg, code
    ok, role, msg, code = validate_role(payload.get('role'))
    if not ok:
        return False, None, msg, code
    password = payload.get('password') or ''
    pwd_min = _password_min()
    if not password or len(password) < pwd_min:
        return False, None, f'密码至少 {pwd_min} 位', 4002
    if password_too_long(password):
        return False, None, f'密码过长（最多 {PASSWORD_MAX_BYTES} 字节）', 4002
    enabled = bool(payload.get('enabled', True))
    # 未显式指定额度时取系统设置的默认额度（设置页可调）
    quota = _parse_quota(payload.get('quota', get_setting('default_quota')))
    return True, {
        'username': username,
        'password': password,
        'role': role,
        'enabled': enabled,
        'quota': quota,
    }, '', 0


def load_update(payload):
    """校验『编辑用户』入参（字段均可选）。返回 (ok, data, message, code)。"""
    payload = payload or {}
    data = {}
    if payload.get('username') is not None:
        ok, username, msg, code = validate_username(payload.get('username'))
        if not ok:
            return False, None, msg, code
        data['username'] = username
    if payload.get('role') is not None:
        ok, role, msg, code = validate_role(payload.get('role'))
        if not ok:
            return False, None, msg, code
        data['role'] = role
    if payload.get('password'):
        password = payload.get('password') or ''
        pwd_min = _password_min()
        if len(password) < pwd_min:
            return False, None, f'密码至少 {pwd_min} 位', 4002
        if password_too_long(password):
            return False, None, f'密码过长（最多 {PASSWORD_MAX_BYTES} 字节）', 4002
        data['password'] = password
    if 'enabled' in payload and payload['enabled'] is not None:
        data['enabled'] = bool(payload['enabled'])
    if payload.get('quota') is not None:
        quota, err = _validate_quota(payload.get('quota'))
        if err:
            return False, None, err, 4005
        data['quota'] = quota
    return True, data, '', 0


def _parse_quota(raw, default=100):
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return default


def _validate_quota(raw):
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return None, '额度必须为整数'
    if v < 0:
        return None, '额度不能为负'
    return v, None
