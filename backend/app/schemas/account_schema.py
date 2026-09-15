# B 平台账号入参校验层（零依赖，风格同 user_schema）
# 登录标识允许手机号或身份证号：仅做非空与长度上限，不做格式强校验（B 平台服务端识别）
from app.utils.validators import validate_recipients

# 已废弃：对应 b_accounts.type，仅保留以兼容旧调用方；界面已无此字段，展示请按 signTasks 派生
VALID_TYPES = ('dorm', 'activity', 'general')
# 账号级推送凭证绑定：{channel: credential_id}，通道白名单
PUSH_CHANNELS = ('serverchan', 'pushplus', 'email')
_MAX_ACCOUNT = 64
_MAX_PASSWORD = 64


def _clean_str(v, limit):
    s = str(v or '').strip()
    return s[:limit] if len(s) <= limit else None


def _clean_push_creds(v):
    """账号级推送凭证绑定清洗。返回 (ok, cleaned|None)。

    绑定项形态（按内容取最简写法，读取端统一归一化）：
      12 / {credId: 12}            → 只绑凭证
      {credId: 12, to: 'a@x.com'}  → 绑凭证并覆盖收件人（仅 email）
      {to: 'a@x.com'}              → 只覆盖收件人，凭证沿用配置套（仅 email）
    None/缺省 → (True, None) 表示不改动；空对象 → (True, {}) 表示清空全部绑定。"""
    if v is None:
        return True, None
    if not isinstance(v, dict):
        return False, None
    out = {}
    for ch, raw in v.items():
        if ch not in PUSH_CHANNELS:
            return False, None
        if raw in (None, ''):
            continue
        if isinstance(raw, dict):
            unknown = set(raw) - {'credId', 'to'}
            if unknown:
                return False, None
            if raw.get('to') not in (None, '') and ch != 'email':
                return False, None  # 收件人只对邮件通道有意义，别的通道带上属脏数据
            cid = raw.get('credId')
            if cid not in (None, ''):
                if isinstance(cid, bool):
                    return False, None
                try:
                    cid = int(cid)
                except (TypeError, ValueError):
                    return False, None
                if cid <= 0:
                    return False, None
            else:
                cid = None
            to = ''
            if raw.get('to') not in (None, ''):
                ok_to, to, _, _ = validate_recipients(raw.get('to'))
                if not ok_to:
                    return False, None
            if cid and to:
                out[ch] = {'credId': cid, 'to': to}
            elif cid:
                out[ch] = cid
            elif to:
                out[ch] = {'to': to}
            continue
        if isinstance(raw, bool):
            return False, None
        try:
            cid = int(raw)
        except (TypeError, ValueError):
            return False, None
        if cid <= 0:
            return False, None
        out[ch] = cid
    return True, out


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
    """新增账号：preflight 基础上允许可选 type（已废弃）/ enabled"""
    ok, data, msg, code = load_preflight(payload)
    if not ok:
        return ok, data, msg, code
    # type 已废弃，前端从不提交，此处仅兼容旧调用方
    type_ = payload.get('type') or 'general'
    if type_ not in VALID_TYPES:
        return False, None, f'账号类型须为 {" / ".join(VALID_TYPES)}', 4101
    data['type'] = type_
    data['enabled'] = bool(payload.get('enabled', True))
    ok_creds, creds = _clean_push_creds(payload.get('pushCreds'))
    if not ok_creds:
        return False, None, '推送凭证绑定不合法', 4105
    if creds is not None:
        data['pushCreds'] = creds
    return True, data, '', 0


def load_update(payload):
    """编辑账号：account/password/enabled 均可选；提供任意一项即参与更新（type 已废弃）"""
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
    # pushCreds 出现即参与更新（空对象 = 清空全部绑定）
    if payload.get('pushCreds') is not None:
        ok_creds, creds = _clean_push_creds(payload.get('pushCreds'))
        if not ok_creds:
            return False, None, '推送凭证绑定不合法', 4105
        data['pushCreds'] = creds
    if not data:
        return False, None, '没有需要更新的字段', 4102
    return True, data, '', 0
