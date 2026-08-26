# 定时任务入参校验层（零依赖，风格同 account_schema / config_schema）
_WEEKDAYS = set(range(1, 8))


def _as_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ('true', '1', 'yes')
    if isinstance(v, int):
        return v == 1
    return False


def _clean_custom(raw):
    """校验自定义参数结构：weekdays(1..7) + hour(0..23) + minute(0..59)。返回 (ok, cfg|None)"""
    if not isinstance(raw, dict):
        return False, None
    wd = raw.get('weekdays')
    if not isinstance(wd, list) or not wd or not all(isinstance(x, int) and x in _WEEKDAYS for x in wd):
        return False, None
    h = raw.get('hour')
    m = raw.get('minute')
    if not isinstance(h, int) or not isinstance(m, int) or not (0 <= h <= 23) or not (0 <= m <= 59):
        return False, None
    cfg = {'hour': h, 'minute': m, 'weekdays': wd}
    if isinstance(raw.get('randomDelayMax'), int):
        cfg['randomDelayMax'] = raw['randomDelayMax']
    return True, cfg


def load_update(payload):
    """更新定时任务：mode / configSetId / custom / enabled 均可选；提供任意一项即参与更新。
    返回 (ok, data, message, code)"""
    payload = payload or {}
    data = {}
    if 'mode' in payload:
        if payload['mode'] not in ('follow', 'custom'):
            return False, None, 'mode 仅支持 follow 或 custom', 4403
        data['mode'] = payload['mode']
    if 'configSetId' in payload:
        v = payload['configSetId']
        if v is not None and not isinstance(v, int):
            return False, None, 'configSetId 应为整数或 null', 4404
        data['config_set_id'] = v
    if 'custom' in payload:
        ok, cfg = _clean_custom(payload['custom'])
        if not ok:
            return False, None, '自定义参数结构不合法（需 weekdays/hour/minute）', 4405
        data['custom'] = cfg
    if 'enabled' in payload:
        data['enabled'] = _as_bool(payload['enabled'])
    if not data:
        return False, None, '没有需要更新的字段', 4406
    return True, data, '', 0
