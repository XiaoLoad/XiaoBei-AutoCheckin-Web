# 定时任务入参校验层（零依赖，风格同 account_schema / config_schema）
_WEEKDAYS = set(range(1, 8))
# overrides 允许覆盖的顶层配置键（与配置套 config 顶层结构对应）；浅合并语义，键整体替换
_OVERRIDE_KEYS = {'time', 'locationId', 'remarks', 'image', 'push', 'advanced', 'fence', 'activity'}
# custom 内联随机延迟上限（F3）：与 config_schema 的 time.randomDelayMax 同口径
_RANDOM_DELAY_MAX_MIN = 0
_RANDOM_DELAY_MAX_LIMIT = 60


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
    if isinstance(raw.get('randomDelayMax'), int) and not isinstance(raw['randomDelayMax'], bool):
        # 随机延迟上限 clamp 到 0~60 分钟（F3）：过大值会让任务近乎永不触发
        cfg['randomDelayMax'] = max(_RANDOM_DELAY_MAX_MIN,
                                    min(_RANDOM_DELAY_MAX_LIMIT, raw['randomDelayMax']))
    return True, cfg


def load_create(payload):
    """显式创建定时任务实例：accountId(整数) + taskType(dorm|activity)。
    返回 (ok, data, message, code)"""
    payload = payload or {}
    account_id = payload.get('accountId')
    task_type = payload.get('taskType')
    if not isinstance(account_id, int) or isinstance(account_id, bool):
        return False, None, 'accountId 应为整数', 4410
    if task_type not in ('dorm', 'activity'):
        return False, None, 'taskType 仅支持 dorm 或 activity', 4411
    return True, {'account_id': account_id, 'task_type': task_type}, '', 0


def load_update(payload):
    """更新定时任务：mode / configSetId / config / custom / enabled / overrides 均可选；提供任意一项即参与更新。
    返回 (ok, data, message, code)"""
    payload = payload or {}
    data = {}
    if 'mode' in payload:
        if payload['mode'] not in ('follow', 'custom', 'standalone'):
            return False, None, 'mode 仅支持 follow / custom / standalone', 4403
        data['mode'] = payload['mode']
    if 'config' in payload:
        # 任务自持完整配置（standalone 权威来源）：与配置套同一套结构兜底清洗——
        # 只放行已知顶层键、校验 time/remarks/image/push/advanced 形状，
        # 防止任务侧成为绕过 config_schema 的脏数据入口（config_json 膨胀/调度器解析异常）
        if not isinstance(payload['config'], dict):
            return False, None, 'config 应为配置对象', 4414
        from app.schemas.config_schema import sanitize_config
        ok_cfg, cfg = sanitize_config(payload['config'])
        if not ok_cfg:
            return False, None, ('任务配置结构不合法：顶层仅接受 '
                                 'time/locationId/remarks/image/push/advanced/fence/'
                                 'activity/presetSetId，且 time.weekdays 必填（1~7）'), 4415
        data['config'] = cfg
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
    if 'overrides' in payload:
        v = payload['overrides']
        if v is not None and not isinstance(v, dict):
            return False, None, 'overrides 应为对象或 null', 4412
        if isinstance(v, dict):
            bad = sorted(k for k in v if k not in _OVERRIDE_KEYS)
            if bad:
                return False, None, f'overrides 含不支持的配置项：{",".join(bad)}', 4413
            v = v or None  # 空对象视为清空全部覆盖
        data['overrides'] = v
    if 'enabled' in payload:
        data['enabled'] = _as_bool(payload['enabled'])
    if not data:
        return False, None, '没有需要更新的字段', 4406
    return True, data, '', 0
