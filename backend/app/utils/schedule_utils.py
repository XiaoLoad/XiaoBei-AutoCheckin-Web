# 定时任务公共工具：从任务实例解析执行时刻（follow 读配置套 / custom 读内联），
# 计算下次执行时间，供前端展示与调度器注册复用（模块 B 展示 / 模块 D 注册共用）。
from datetime import timedelta

from app.extensions import db
from app.models.user import now_cst


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
