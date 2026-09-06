# 配置套入参校验层（零依赖，风格同 account_schema）。
# 结构完整性由前端 validateConfig 负责 UX 提示；此处做类型/边界兜底，
# 只放行已知顶层键，防脏数据入库膨胀 config_json。
_ALLOWED_TOP = {'presetSetId', 'time', 'locationId', 'remarks', 'image', 'push', 'advanced',
                'fence', 'activity'}
_WEEKDAYS = set(range(1, 8))
_MAX_NAME = 64


def _clean_name(v):
    s = str(v or '').strip()
    return s[:_MAX_NAME] if 0 < len(s) <= _MAX_NAME else None


def _as_bool(v):
    """宽松解析布尔：接受 Python bool / 'true'|'1'|'yes' 字符串 / 整数 1。"""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ('true', '1', 'yes')
    if isinstance(v, int):
        return v == 1
    return False


def _clean_activity(act):
    """activity 专属块兜底清洗（活动签到课表驱动调度）。返回 (ok, normalized|None)。
    配置套与任务类型解耦（同一套可绑定 dorm/activity），此块对 dorm 任务无消费者、
    调度器仅对 activity 读取；strategy=course 时校验边界并补默认值。"""
    if not isinstance(act, dict):
        return False, None
    strategy = act.get('strategy') or 'fixed'
    if strategy not in ('fixed', 'course'):
        return False, None
    out = {'strategy': strategy}
    if strategy == 'course':
        course = act.get('course') or {}
        if not isinstance(course, dict):
            return False, None
        cleaned = {}
        for key, lo, hi, default in (('leadMinutes', 0, 120, 60),
                                     ('tailMinutes', 0, 120, 30),
                                     ('pollIntervalSec', 30, 1800, 120)):
            v = course.get(key)
            if v is None:
                cleaned[key] = default
            elif isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi:
                cleaned[key] = v
            else:
                return False, None
        exclude = course.get('excludeCourses')
        if exclude is None:
            exclude = []
        if not isinstance(exclude, list) or any(not isinstance(x, str) for x in exclude):
            return False, None
        cleaned['excludeCourses'] = exclude
        # 块级排除（"周|课程|小节段"键）：同一门课可按上课时段单独排除（如只签第一节课）
        exclude_blocks = course.get('excludeBlocks')
        if exclude_blocks is None:
            exclude_blocks = []
        if not isinstance(exclude_blocks, list) or any(not isinstance(x, str) for x in exclude_blocks):
            return False, None
        cleaned['excludeBlocks'] = exclude_blocks
        weekdays = course.get('weekdays')
        if weekdays is None:
            weekdays = []
        if not isinstance(weekdays, list) or any(
                not isinstance(x, int) or x not in _WEEKDAYS for x in weekdays):
            return False, None
        cleaned['weekdays'] = weekdays   # 空 = 不限星期
        out['course'] = cleaned
        fallback = act.get('fallback') or {}
        if not isinstance(fallback, dict):
            return False, None
        out['fallback'] = {'enabled': bool(fallback.get('enabled', True))}
    return True, out


def sanitize_config(raw):
    """配置体兜底清洗。返回 (ok, cfg_or_None)"""
    if not isinstance(raw, dict):
        return False, None
    if set(raw) - _ALLOWED_TOP:
        return False, None
    raw = dict(raw)
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
    # fence 为新增可选块（旧数据/旧客户端不带，执行端默认开）；出现时须为对象
    if 'fence' in raw and not isinstance(raw['fence'], dict):
        return False, None
    # activity 为活动签到专属可选块（课表驱动调度）；出现时清洗归一化，非法整体拒绝
    if 'activity' in raw:
        ok_act, act = _clean_activity(raw['activity'])
        if not ok_act:
            return False, None
        raw['activity'] = act
    return True, raw


def load_create(payload):
    """新增配置套：name 必填（≤64 字），config 结构合法，taskType 仅 dorm|activity（创建后锁定）。
    返回 (ok, data, message, code)"""
    payload = payload or {}
    name = _clean_name(payload.get('name'))
    if not name:
        return False, None, '配置套名称不能为空（64 字以内）', 4200
    ok, cfg = sanitize_config(payload.get('config'))
    if not ok:
        return False, None, '配置体结构不合法', 4201
    task_type = payload.get('taskType') or 'dorm'
    if task_type not in ('dorm', 'activity'):
        return False, None, '配置套类型仅支持寝室（dorm）或活动（activity）', 4204
    data = {'name': name, 'config': cfg, 'task_type': task_type}
    if 'isDefault' in payload:
        data['is_default'] = _as_bool(payload['isDefault'])
    return True, data, '', 0


def load_update(payload):
    """更新配置套：name / config 均可选；提供任意一项即参与更新。
    taskType 不接受更新——类型创建后锁定（改类型会造成绑定错配，需另存为新套）。"""
    payload = payload or {}
    payload.pop('taskType', None)
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
    if 'isDefault' in payload:
        data['is_default'] = _as_bool(payload['isDefault'])
    if not data:
        return False, None, '没有需要更新的字段', 4202
    return True, data, '', 0
