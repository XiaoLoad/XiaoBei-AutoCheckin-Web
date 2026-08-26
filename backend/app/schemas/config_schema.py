# 配置套入参校验层（零依赖，风格同 account_schema）。
# 结构完整性由前端 validateConfig 负责 UX 提示；此处做类型/边界兜底，
# 只放行已知顶层键，防脏数据入库膨胀 config_json。
_ALLOWED_TOP = {'presetSetId', 'time', 'locationId', 'remarks', 'image', 'push', 'advanced'}
_WEEKDAYS = set(range(1, 8))
_MAX_NAME = 64


def _clean_name(v):
    s = str(v or '').strip()
    return s[:_MAX_NAME] if 0 < len(s) <= _MAX_NAME else None


def sanitize_config(raw):
    """配置体兜底清洗。返回 (ok, cfg_or_None)"""
    if not isinstance(raw, dict):
        return False, None
    if set(raw) - _ALLOWED_TOP:
        return False, None
    t = raw.get('time')
    if not isinstance(t, dict):
        return False, None
    wd = t.get('weekdays')
    if not isinstance(wd, list) or not wd or not all(isinstance(x, int) and x in _WEEKDAYS for x in wd):
        return False, None
    rem = raw.get('remarks')
    if not isinstance(rem, list) or any(not isinstance(x, str) for x in rem):
        return False, None
    for blk in ('image', 'push', 'advanced'):
        if not isinstance(raw.get(blk), dict):
            return False, None
    return True, raw


def load_create(payload):
    """新增配置套：name 必填（≤64 字），config 结构合法。返回 (ok, data, message, code)"""
    payload = payload or {}
    name = _clean_name(payload.get('name'))
    if not name:
        return False, None, '配置套名称不能为空（64 字以内）', 4200
    ok, cfg = sanitize_config(payload.get('config'))
    if not ok:
        return False, None, '配置体结构不合法', 4201
    return True, {'name': name, 'config': cfg}, '', 0


def load_update(payload):
    """更新配置套：name / config 均可选；提供任意一项即参与更新"""
    payload = payload or {}
    data = {}
    if payload.get('name') is not None:
        name = _clean_name(payload['name'])
        if not name:
            return False, None, '配置套名称不能为空（64 字以内）', 4200
        data['name'] = name
    if payload.get('config') is not None:
        ok, cfg = sanitize_config(payload['config'])
        if not ok:
            return False, None, '配置体结构不合法', 4201
        data['config'] = cfg
    if not data:
        return False, None, '没有需要更新的字段', 4202
    return True, data, '', 0
