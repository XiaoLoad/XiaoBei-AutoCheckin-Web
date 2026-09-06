# 定时任务公共工具：从任务实例解析执行时刻（follow 读配置套 / custom 读内联），
# 计算下次执行时间，供前端展示与调度器注册复用（模块 B 展示 / 模块 D 注册共用）。
from datetime import timedelta

from app.extensions import db
from app.models.user import now_cst


def resolve_config(schedule):
    """解析任务真实执行配置（调度器与课表窗口展开共用同一口径）。
    standalone（config_json 非空）= 任务自持完整配置，权威来源；
    follow = 配置套 + 字段级覆盖浅合并（overrides 顶层键替换套内同键，未覆盖键继续跟随配置套）；
    custom = 内联 time-only。缺配置返回 None。"""
    if schedule.has_own_config:
        return schedule.config or {}
    if schedule.mode == 'follow':
        if not schedule.config_set_id:
            return None
        from app.models.config_set import ConfigSet
        cs = db.session.get(ConfigSet, schedule.config_set_id)
        if cs is None:
            return None
        return {**(cs.config or {}), **(schedule.overrides or {})}
    return schedule.custom or {}


def resolve_activity_cfg(schedule):
    """解析 activity 专属配置块（课表驱动调度）。返回归一化 dict 或 None：
    None 表示非 activity 任务 / strategy=fixed（走原有固定 cron 语义）。
    归一化字段：lead/tail（分钟）、poll（秒）、exclude（课程名列表）、
    weekdays（None=不限，或 1..7 列表）、fallbackEnabled（每日兜底单次查询）。"""
    if schedule.task_type != 'activity':
        return None
    act = (resolve_config(schedule) or {}).get('activity') or {}
    if act.get('strategy') != 'course':
        return None

    def _clamp_int(v, lo, hi, default):
        try:
            v = int(v)
        except (TypeError, ValueError):
            return default
        return max(lo, min(hi, v))

    course = act.get('course') or {}
    fallback = act.get('fallback') or {}
    weekdays = course.get('weekdays')
    if isinstance(weekdays, list) and weekdays:
        weekdays = sorted({w for w in weekdays if isinstance(w, int) and 1 <= w <= 7}) or None
    else:
        weekdays = None
    exclude = [str(x).strip() for x in (course.get('excludeCourses') or []) if str(x).strip()]
    return {
        'lead': _clamp_int(course.get('leadMinutes'), 0, 120, 15),
        'tail': _clamp_int(course.get('tailMinutes'), 0, 120, 30),
        'poll': _clamp_int(course.get('pollIntervalSec'), 30, 1800, 120),
        'exclude': exclude,
        'weekdays': weekdays,
        'fallbackEnabled': bool(fallback.get('enabled', True)),
    }


def _extract_schedule_time(schedule):
    """返回 (hour, minute, weekdays[1..7])，缺失返回 (None, None, [])。
    standalone（config_json 非空）从任务自持配置取 time；follow 与调度器 _resolve 同口径：
    配置套 + 字段级覆盖浅合并后再取 time；custom 从内联 time-only 取。"""
    if schedule.has_own_config:
        cfg = schedule.config or {}
        t = cfg.get('time') or {}
        sign_time = t.get('signTime') or {}
        return sign_time.get('hour'), sign_time.get('minute'), t.get('weekdays') or []
    if schedule.mode == 'follow':
        cfg = {}
        if schedule.config_set_id:
            from app.models.config_set import ConfigSet
            cs = db.session.get(ConfigSet, schedule.config_set_id)
            if cs:
                cfg = dict(cs.config or {})
        cfg.update(schedule.overrides or {})
        t = cfg.get('time') or {}
        sign_time = t.get('signTime') or {}
        hour = sign_time.get('hour')
        minute = sign_time.get('minute')
        weekdays = t.get('weekdays') or []
    else:
        cfg = schedule.custom
        hour = cfg.get('hour')
        minute = cfg.get('minute')
        weekdays = cfg.get('weekdays') or []
    return hour, minute, weekdays


def extract_schedule_time(schedule):
    """解析任务执行时刻，返回 (hour, minute, weekdays[1..7])；供调度器注册 cron 复用，
    保证前端展示与调度器实际注册使用同一套 resolve 逻辑。"""
    return _extract_schedule_time(schedule)


def extract_jitter_minutes(schedule):
    """随机延迟上限（分钟）：standalone（config_json 非空）与 follow（配置套+字段级覆盖
    浅合并，overrides 顶层键整体替换）从解析后配置的 time.randomDelayMax 取；
    custom 从内联顶层取。调度器注册 CronTrigger.jitter 与任务详情展示（nextRunJitterMin）
    共用同一口径，避免「展示与实际注册各算各的」漂移。"""
    if schedule.mode == 'custom':
        return int((schedule.custom or {}).get('randomDelayMax') or 0)
    if schedule.has_own_config:
        cfg = schedule.config or {}
    elif schedule.mode == 'follow':
        cfg = {}
        if schedule.config_set_id:
            from app.models.config_set import ConfigSet
            cs = db.session.get(ConfigSet, schedule.config_set_id)
            if cs:
                cfg = dict(cs.config or {})
        cfg.update(schedule.overrides or {})
    else:
        cfg = {}
    return int((cfg.get('time') or {}).get('randomDelayMax') or 0)


def compute_next_run(schedule, base=None):
    """基于当前/给定时刻计算下次执行时间（朴素中国本地时间）。无有效时刻返回 None。"""
    hour, minute, weekdays = _extract_schedule_time(schedule)
    if hour is None or minute is None:
        return None
    try:
        hour = int(hour)
        minute = int(minute)
    except (TypeError, ValueError):
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    # 配置 weekdays：1=周一..7=周日 → Python weekday()：0=周一..6=周日
    target_wds = set()
    for w in weekdays:
        try:
            w = int(w)
        except (TypeError, ValueError):
            continue
        if 1 <= w <= 7:
            target_wds.add(w - 1)
    if not target_wds:
        return None
    base = base or now_cst()
    for delta in range(0, 8):
        cand = base + timedelta(days=delta)
        if cand.weekday() not in target_wds:
            continue
        dt = cand.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if delta == 0 and dt <= base:
            continue
        return dt
    return None
