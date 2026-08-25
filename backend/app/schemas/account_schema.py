# B 平台账号入参校验层（零依赖，风格同 user_schema）
# 登录标识允许手机号或身份证号：仅做非空与长度上限，不做格式强校验（B 平台服务端识别）
VALID_TYPES = ('dorm', 'activity', 'general')
_MAX_ACCOUNT = 64
_MAX_PASSWORD = 64


def _clean_str(v, limit):
    s = str(v or '').strip()
    return s[:limit] if len(s) <= limit else None


def load_preflight(payload):
    """凭据预检：account + password 必填。返回 (ok, data, message, code)"""
    payload = payload or {}
    account = _clean_str(payload.get('account'), _MAX_ACCOUNT)
    password = str(payload.get('password') or '')
    if not account:
        return False, None, '请填写 B 平台账号', 4100
    if not password:
        return False, None, '请填写 B 平台密码', 4100
    return True, {'account': account, 'password': password}, '', 0


def load_create(payload):
    """新增账号：preflight 基础上允许可选 type / enabled"""
    ok, data, msg, code = load_preflight(payload)
    if not ok:
        return ok, data, msg, code
    type_ = payload.get('type') or 'general'
    if type_ not in VALID_TYPES:
        return False, None, f'账号类型须为 {" / ".join(VALID_TYPES)}', 4101
    data['type'] = type_
    data['enabled'] = bool(payload.get('enabled', True))
    return True, data, '', 0


def load_update(payload):
    """编辑账号：account/password/type/enabled 均可选；提供任意一项即参与更新"""
    payload = payload or {}
    data = {}
    if payload.get('account') is not None:
        account = _clean_str(payload.get('account'), _MAX_ACCOUNT)
        if not account:
            return False, None, 'B 平台账号不能为空', 4100
        data['account'] = account
    if payload.get('password') is not None:
        password = str(payload.get('password') or '')
        if not password:
            return False, None, '密码不能为空', 4100
        data['password'] = password
    if payload.get('type') is not None:
        if payload['type'] not in VALID_TYPES:
            return False, None, f'账号类型须为 {" / ".join(VALID_TYPES)}', 4101
        data['type'] = payload['type']
    if payload.get('enabled') is not None:
        data['enabled'] = bool(payload['enabled'])
    if not data:
        return False, None, '没有需要更新的字段', 4102
    return True, data, '', 0
