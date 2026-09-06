# 教务课表同步编排（多账号）：全局串行队列 + 登录间隔随机化（避免并发登录触发风控）、
# 失败隔离（单账号连续失败只降级自身，不阻断队列）、学期/周历学校级共享缓存、
# 以及"当日活动签到轮询窗口"展开（课表 × 作息时间 → 每任务每课程一个时间窗）。
import hashlib
import json
import logging
import random
import threading
import time
from datetime import datetime, timedelta

from app.extensions import db
from app.models import ActivityWindow, BAccount, JwAccount, JwSemester, JwTimetable, Schedule
from app.models.system_config import SystemConfig
from app.models.user import now_cst
from app.services.jwxt import get_client
from app.services.jwxt.base import JwxtError
from app.utils.schedule_utils import resolve_activity_cfg

log = logging.getLogger('jwxt.sync')

# 全局串行锁：多账号同时登录教务易触发风控/验证码，同步一律排队执行
_SYNC_LOCK = threading.Lock()
_LAST_LOGIN_MONOTONIC = 0.0
# 相邻两次教务登录的最小间隔（秒）：随机 3~8s，进程内生效
_LOGIN_GAP_RANGE = (3, 8)

_FAILS_BEFORE_ATTENTION = 3

# 异步同步执行中登记：b_account_id → True（队列去重 + GET 概览回显"同步中"）。
# 教务网偶发秒级挂起（单请求最坏 20s×2 次重试 × 3 个页面），同步请求必须异步化，
# 否则前端 HTTP 先超时误报"网络错误"而后端实际成功。
_RUNNING = set()
_RUNNING_LOCK = threading.Lock()

# 学校实测作息表（2026-09 起，设计文档 §2.4）：小节 → (开始, 结束)。
# 节次间隔不均匀（08:20/09:15/10:25/11:20/14:00/14:55/16:00/16:55/18:50…），
# 不能按固定节奏推算，必须整表配置；system_configs.class_period_times(JSON) 可整体覆盖。
DEFAULT_PERIOD_TIMES = {
    1: ('08:20', '09:05'), 2: ('09:15', '10:00'), 3: ('10:25', '11:10'), 4: ('11:20', '12:05'),
    5: ('14:00', '14:45'), 6: ('14:55', '15:40'), 7: ('16:00', '16:45'), 8: ('16:55', '17:40'),
    9: ('18:50', '19:35'), 10: ('19:45', '20:30'), 11: ('20:45', '21:30'), 12: ('21:45', '22:30'),
}
_PERIOD_TIMES_KEY = 'class_period_times'


def get_period_times():
    """生效作息表：system_configs 的 JSON 覆盖优先，非法/缺失回退默认表。
    返回 {小节号: (datetime.time 开始, datetime.time 结束)}。"""
    times = dict(DEFAULT_PERIOD_TIMES)
    try:
        row = SystemConfig.query.filter_by(key=_PERIOD_TIMES_KEY).first()
        if row is not None and (row.value or '').strip():
            override = json.loads(row.value)
            if isinstance(override, dict):
                for k, v in override.items():
                    try:
                        idx = int(k)
                        start, end = str(v).split('-')
                        sh, sm = start.strip().split(':')
                        eh, em = end.strip().split(':')
                        from datetime import time as dtime
                        times[idx] = (dtime(int(sh), int(sm)), dtime(int(eh), int(em)))
                    except (ValueError, TypeError):
                        continue
    except Exception:
        pass
    from datetime import time as dtime
    fixed = {}
    for idx, pair in times.items():
        s, e = pair
        if isinstance(s, str):
            sh, sm = s.split(':')
            s = dtime(int(sh), int(sm))
        if isinstance(e, str):
            eh, em = e.split(':')
            e = dtime(int(eh), int(em))
        fixed[idx] = (s, e)
    return fixed


def _content_hash(entry_dicts):
    canonical = json.dumps(sorted(
        (json.dumps(d, sort_keys=True, ensure_ascii=False) for d in entry_dicts)), ensure_ascii=False)
    return hashlib.md5(canonical.encode('utf-8')).hexdigest()


def sync_b_account(b_account_id, min_login_gap=True):
    """对指定 B 平台账号执行一次教务同步（阻塞版，进全局串行队列）。
    返回同步摘要 dict；失败抛 JwxtError（状态已落库）。接口层请用 queue_sync 异步版。"""
    jw = JwAccount.query.filter_by(b_account_id=b_account_id).first()
    if jw is None:
        raise JwxtError('unknown', '该账号未绑定教务系统')
    with _SYNC_LOCK:
        return _sync_locked(jw, min_login_gap=min_login_gap)


def is_sync_running(b_account_id):
    with _RUNNING_LOCK:
        return int(b_account_id) in _RUNNING


def queue_sync(b_account_id, flask_app):
    """提交一次后台同步（异步）：已在执行/排队时返回 False（幂等，不重复排队）。
    线程内自行进入应用上下文；全局串行锁保证多账号按提交顺序依次执行。"""
    bid = int(b_account_id)
    with _RUNNING_LOCK:
        if bid in _RUNNING:
            return False
        _RUNNING.add(bid)

    def _worker():
        try:
            with flask_app.app_context():
                with _SYNC_LOCK:
                    jw = JwAccount.query.filter_by(b_account_id=bid).first()
                    if jw is not None:
                        _sync_locked(jw, min_login_gap=True)
        except Exception:
            log.exception('账号 %s 后台同步线程异常（状态已落库）', bid)
        finally:
            with _RUNNING_LOCK:
                _RUNNING.discard(bid)

    threading.Thread(target=_worker, name=f'jwxt-sync-{bid}', daemon=True).start()
    return True


def _sync_locked(jw, min_login_gap=True):
    global _LAST_LOGIN_MONOTONIC
    client = get_client()
    if min_login_gap and _LAST_LOGIN_MONOTONIC:
        gap = random.uniform(*_LOGIN_GAP_RANGE)
        elapsed = time.monotonic() - _LAST_LOGIN_MONOTONIC
        if elapsed < gap:
            time.sleep(gap - elapsed)
    try:
        session = client.login(jw.student_no, jw.get_password())
        _LAST_LOGIN_MONOTONIC = time.monotonic()

        semester = client.fetch_current_semester(session)
        sem_row = JwSemester.query.filter_by(semester=semester).first()
        if sem_row is None:
            week1_monday, total_weeks = client.fetch_week_calendar(session, semester)
            sem_row = JwSemester(semester=semester, week1_monday=week1_monday,
                                 total_weeks=total_weeks)
            db.session.add(sem_row)

        entries = client.fetch_timetable(session, semester)
        entry_dicts = [e.to_dict() for e in entries]
        content_hash = _content_hash(entry_dicts)
        tt = JwTimetable.query.filter_by(b_account_id=jw.b_account_id, semester=semester).first()
        if tt is None:
            tt = JwTimetable(b_account_id=jw.b_account_id, semester=semester)
            db.session.add(tt)
        changed = tt.content_hash != content_hash
        tt.set_entries(entry_dicts)
        tt.content_hash = content_hash
        tt.synced_at = now_cst()

        jw.status = 'ok'
        jw.last_error = ''
        jw.fail_count = 0
        jw.last_login_at = now_cst()
        jw.last_sync_at = now_cst()
        db.session.commit()

        # 同步成功后立即展开该账号的活动签到窗口（仅影响 strategy=course 的任务）
        expanded = expand_windows_for_account(jw.b_account_id)
        log.info('账号 %s 教务同步完成：学期 %s，课程 %d 条%s，展开窗口 %d 个',
                 jw.b_account_id, semester, len(entry_dicts),
                 '（内容有更新）' if changed else '', expanded)
        return {'semester': semester, 'courses': len(entry_dicts),
                'changed': changed, 'windows': expanded}
    except JwxtError as e:
        db.session.rollback()
        jw.fail_count = (jw.fail_count or 0) + 1
        jw.last_error = e.message[:250]
        if jw.fail_count >= _FAILS_BEFORE_ATTENTION:
            jw.status = 'needs_attention'
        db.session.commit()
        log.warning('账号 %s 教务同步失败（第 %d 次）：%s', jw.b_account_id, jw.fail_count, e.message)
        raise
    except Exception as e:
        db.session.rollback()
        jw.fail_count = (jw.fail_count or 0) + 1
        jw.last_error = f'同步异常：{e}'[:250]
        if jw.fail_count >= _FAILS_BEFORE_ATTENTION:
            jw.status = 'needs_attention'
        db.session.commit()
        log.exception('账号 %s 教务同步异常', jw.b_account_id)
        raise JwxtError('unknown', f'同步异常：{e}')


def unbind_b_account(b_account_id):
    """解绑：清理凭证、课表快照，并清空该账号任务的当日窗口（课程策略任务回落兜底行为）。"""
    jw = JwAccount.query.filter_by(b_account_id=b_account_id).first()
    if jw is None:
        return
    schedule_ids = [s.id for s in Schedule.query.filter_by(account_id=b_account_id).all()]
    if schedule_ids:
        ActivityWindow.query.filter(ActivityWindow.schedule_id.in_(schedule_ids)).delete(
            synchronize_session=False)
    JwTimetable.query.filter_by(b_account_id=b_account_id).delete(synchronize_session=False)
    db.session.delete(jw)
    db.session.commit()


# ===== 当日活动签到窗口展开 =====

def block_key(entry):
    """课表时段块的稳定键："星期|课程名|小节段"（小节段为 min-max 紧凑形式）。
    块级排除（excludeBlocks）以此为粒度：同一门课的不同上课时段可单独排除。"""
    secs = entry.sections or []
    if not secs:
        return ''
    seg = f'{min(secs)}-{max(secs)}' if len(secs) > 1 else f'{min(secs)}'
    return f'{entry.weekday}|{entry.course}|{seg}'


def current_week_of(today, sem_row):
    """教学周次：第 1 周周一为基准；周历之外（寒暑假）返回 0。"""
    if today < sem_row.week1_monday:
        return 0
    week = (today - sem_row.week1_monday).days // 7 + 1
    if week > (sem_row.total_weeks or 0) > 0:
        return 0
    return week


def expand_windows_for_account(b_account_id, today=None):
    """为该账号所有启用中的 activity 任务展开当日窗口。返回展开的窗口数。"""
    today = today or now_cst().date()
    total = 0
    schedules = Schedule.query.filter_by(account_id=b_account_id, task_type='activity', enabled=True).all()
    for s in schedules:
        total += expand_windows_for_schedule(s, today=today)
    db.session.commit()
    return total


def expand_windows_for_schedule(schedule, today=None):
    """单个任务的当日窗口展开：课表条目 × 作息时间 × 提前/延续/过滤 → 窗口行。
    幂等重建，但保留已存在窗口的 done / last_polled_at（轮询状态不因重复展开而丢失）。
    非 course 策略 / 未同步课表 / 假期 → 当日窗口清空（仅剩 fallback 兜底）。返回窗口数。"""
    today = today or now_cst().date()
    existing = ActivityWindow.query.filter_by(schedule_id=schedule.id, date=today).all()
    keep_state = {(w.course_name, w.sections, w.start_at, w.end_at): w for w in existing}

    new_rows = []
    act = resolve_activity_cfg(schedule)
    if act is not None and schedule.enabled:
        tt = (JwTimetable.query
              .filter_by(b_account_id=schedule.account_id)
              .order_by(JwTimetable.synced_at.desc())
              .first())
        sem_row = JwSemester.query.filter_by(semester=tt.semester).first() if tt else None
        if tt is not None and sem_row is not None:
            week = current_week_of(today, sem_row)
            if week > 0:
                times = get_period_times()
                max_idx = max(times) if times else 0
                weekday = today.isoweekday()
                exclude_block_set = set(act['excludeBlocks'])
                for e in tt.entries:
                    if e.weekday != weekday or week not in e.weeks:
                        continue
                    if act['weekdays'] is not None and weekday not in act['weekdays']:
                        continue
                    if e.course in act['exclude']:
                        continue
                    if exclude_block_set and block_key(e) in exclude_block_set:
                        continue
                    if not e.sections:
                        continue
                    if min(e.sections) > max_idx:
                        continue
                    start_t = times[min(e.sections)][0]
                    end_t = times[min(max(e.sections), max_idx)][1]
                    start_at = datetime.combine(today, start_t) - timedelta(minutes=act['lead'])
                    end_at = datetime.combine(today, end_t) + timedelta(minutes=act['tail'])
                    secs = f'{min(e.sections)}-{max(e.sections)}'
                    row = ActivityWindow(
                        schedule_id=schedule.id, date=today,
                        start_at=start_at, end_at=end_at,
                        course_name=e.course[:64], sections=secs,
                        # 轮询起点抖动：同窗口多账号错开首个查询时刻（±一个轮询间隔内）
                        last_polled_at=start_at - timedelta(seconds=random.uniform(0, act['poll'])),
                        done=False,
                    )
                    prev = keep_state.get((row.course_name, row.sections, row.start_at, row.end_at))
                    if prev is not None:
                        row.done = prev.done
                        row.last_polled_at = prev.last_polled_at
                    new_rows.append(row)

    for w in existing:
        db.session.delete(w)
    for row in new_rows:
        db.session.add(row)
    db.session.commit()
    return len(new_rows)


def expand_windows_daily():
    """每日例行：清理过期窗口 + 为全部 course 策略活动任务重建当日窗口。调度器每日调用。"""
    today = now_cst().date()
    removed = (ActivityWindow.query
               .filter(ActivityWindow.date < today)
               .delete(synchronize_session=False))
    db.session.commit()
    schedules = Schedule.query.filter_by(task_type='activity', enabled=True).all()
    expanded = 0
    for s in schedules:
        if resolve_activity_cfg(s) is None:
            continue
        expanded += expand_windows_for_schedule(s, today=today)
    if removed or expanded:
        log.info('活动窗口每日展开：清理过期 %d 条，重建当日 %d 条', removed, expanded)
    return expanded


def jwxt_overview(b_account_id):
    """账号的教务绑定与课表概览（接口回显用，仅读库不发请求）。未绑返回 None。"""
    jw = JwAccount.query.filter_by(b_account_id=b_account_id).first()
    if jw is None:
        return None
    tt = (JwTimetable.query
          .filter_by(b_account_id=b_account_id)
          .order_by(JwTimetable.synced_at.desc())
          .first())
    sem_row = JwSemester.query.filter_by(semester=tt.semester).first() if tt else None
    courses = []
    if tt is not None:
        seen = {}
        for e in tt.entries:
            # 按块+周次去重：同一时段块的不同周次是独立条目（如第 3、4 周各上一次的课
            # 都要出现在课表视图）；blockKey 不含周次——块级排除按"时段"语义，同一
            # 块的所有周次联动排除
            key = block_key(e)
            if not key:
                continue
            weeks_tag = ','.join(str(w) for w in sorted(e.weeks))
            full_key = f'{key}|{weeks_tag}'
            if full_key in seen:
                continue
            seen[full_key] = {
                'course': e.course, 'weeks': sorted(e.weeks), 'weekday': e.weekday,
                'sections': sorted(e.sections), 'blockKey': key,
                'teacher': e.teacher, 'room': e.room,
            }
        courses = sorted(seen.values(), key=lambda x: (x['weekday'], min(x['sections'])))
    acc = db.session.get(BAccount, b_account_id)
    return {
        'bound': True,
        'account': jw.to_dict(),
        'semester': sem_row.to_dict() if sem_row else None,
        'courses': courses,
        # 生效作息表（小节 → 钟点），供前端课表视图渲染时间段；键为字符串化小节号
        'periodTimes': {str(k): [v[0].strftime('%H:%M'), v[1].strftime('%H:%M')]
                        for k, v in sorted(get_period_times().items())},
        'timetableSyncedAt': tt.synced_at.strftime('%Y-%m-%d %H:%M') if tt and tt.synced_at else '',
        'className': (acc.profile.get('className') or '') if acc else '',
        'syncRunning': is_sync_running(b_account_id),
    }
