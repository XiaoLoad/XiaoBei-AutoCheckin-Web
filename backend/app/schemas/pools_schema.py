# 资源池入参校验层（零依赖，风格同 account_schema）
# 凭证脱敏约定：回显时密文字段变 `••••尾4位`；更新时该前缀视为「未修改」占位被丢弃，
# 库中旧值与用户新填的非密文字段合并后再校验必填（路由层负责合并，见 Task 7）。
import re

_CHANNELS = ('serverchan', 'pushplus', 'email')
_CRED_REQUIRED_FIELDS = {
    'serverchan': ['serverchanKey'],
    'pushplus': ['pushplusToken'],
    'email': ['emailSmtp', 'emailFrom', 'emailPass', 'emailTo'],
}
_SECRET_KEYS = ('serverchanKey', 'pushplusToken', 'emailPass')
_MASK_RE = re.compile(r'^••••')
_COMPOSITE = (dict, list, tuple, set)


def _field_str(v):
    """字段值仅收标量；dict/list 等复合类型返回 None 由调用方整体拒绝，防 str() 吞成脏串"""
    if isinstance(v, _COMPOSITE):
        return None
    return str(v or '').strip()


def load_location(payload):
    """位置池入参：name/lat/lng/address 必填，offset 0~500 米默认 10"""
    payload = payload or {}
    name = str(payload.get('name') or '').strip()[:64]
    if not name:
        return False, None, '位置名称不能为空', 4300

    def _f(key):
        try:
            v = float(payload.get(key))
            return v if -180.0 <= v <= 180.0 else None
        except (TypeError, ValueError, OverflowError):
            return None

    lat, lng = _f('lat'), _f('lng')
    if lat is None or lng is None:
        return False, None, '经纬度须为有效数字', 4301
    address = str(payload.get('address') or '').strip()[:255]
    if not address:
        return False, None, '地址号不能为空', 4302
    try:
        offset = int(payload.get('offset', 10))
    except (TypeError, ValueError, OverflowError):
        offset = 10
    offset = min(max(offset, 0), 500)
    data = {'name': name, 'address': address,
            'lat': lat, 'lng': lng, 'offset_m': offset,
            'enabled': bool(payload.get('enabled', True))}
    return True, data, '', 0


def load_ua(payload):
    """UA 模板入参：content 必填，remark ≤255"""
    payload = payload or {}
    content = str(payload.get('content') or '').strip()
    if not content:
        return False, None, 'UA 内容不能为空', 4310
    remark = str(payload.get('remark') or '').strip()[:255]
    return True, {'content': content, 'remark': remark}, '', 0


def load_credential(payload):
    """新增凭证：channel 合法且必填字段齐全；只收编必填键防脏数据"""
    payload = payload or {}
    channel = payload.get('channel')
    if channel not in _CHANNELS:
        return False, None, f'推送通道须为 {" / ".join(_CHANNELS)}', 4320
    name = str(payload.get('name') or '').strip()[:64]
    if not name:
        return False, None, '凭证名称不能为空', 4320
    fields = payload.get('fields')
    if not isinstance(fields, dict):
        return False, None, '凭证内容缺失', 4321
    clean = {}
    for k in _CRED_REQUIRED_FIELDS[channel]:
        v = _field_str(fields.get(k))
        if v is None:
            return False, None, f'字段 {k} 内容格式无效', 4321
        if not v:
            return False, None, f'缺少必填项：{k}', 4321
        clean[k] = v[:255]
    return True, {'channel': channel, 'name': name, 'fields': clean}, '', 0


def load_credential_update(payload):
    """更新凭证：channel/name/fields 可选；fields 内脱敏占位值直接丢弃"""
    payload = payload or {}
    data = {}
    if payload.get('channel') is not None:
        if payload['channel'] not in _CHANNELS:
            return False, None, f'推送通道须为 {" / ".join(_CHANNELS)}', 4320
        data['channel'] = payload['channel']
    if payload.get('name') is not None:
        name = str(payload['name']).strip()[:64]
        if not name:
            return False, None, '凭证名称不能为空', 4320
        data['name'] = name
    if payload.get('fields') is not None:
        if not isinstance(payload['fields'], dict):
            return False, None, '凭证内容缺失', 4321
        clean = {}
        for k, v in payload['fields'].items():
            v = _field_str(v)
            if v is None:
                return False, None, f'字段 {k} 内容格式无效', 4321
            if _MASK_RE.match(v):
                continue
            clean[str(k)[:64]] = v[:255]
        data['fields'] = clean
    if not data:
        return False, None, '没有需要更新的字段', 4322
    return True, data, '', 0


def mask_fields(fields):
    """密文字段脱敏为 ••••尾4位；非密文字段原样"""
    out = {}
    for k, v in (fields or {}).items():
        v = str(v or '')
        out[k] = f'••••{v[-4:]}' if k in _SECRET_KEYS else v
    return out


def required_missing(channel, fields):
    if not isinstance(fields, dict):
        fields = {}
    return [k for k in _CRED_REQUIRED_FIELDS.get(channel, [])
            if not str((fields or {}).get(k) or '').strip()]
