# T5/T6 回归：提交读超时不重发 + 活动窗口展开防重复
#
# T5：submit_checkin 的重试循环此前对 requests.RequestException 全家退避重试，
#     读超时（请求已发出、平台可能已受理）重发会重复提交签到。现读超时立即终止；
#     连接类失败（请求未抵达平台）仍可安全重试。
# T6：窗口展开是「读现有 → 删除 → 插入 → commit」删插事务，进程内全局锁串行化
#     并发入口；数据库唯一约束兜住锁外路径。并发展开不得产生重复窗口行。
import threading
from uuid import uuid4

import pytest
import requests

from app.extensions import db
from app.models import ActivityWindow, BAccount, ConfigSet, Schedule, User
from app.services import scheduler as sch
from app.services.b_platform.real import RealAdapter, _MAX_NET_RETRIES
from app.services.jwxt import sync as jw_sync
from app.models.user import now_cst


# ==================== T5：提交读超时不重发 ====================

def _submit_adapter():
    """最小可调用 adapter（submit_checkin 只用到 _module/_headers 等纯函数路径）"""
    return RealAdapter()


def test_submit_read_timeout_raises_immediately(monkeypatch):
    """读超时：请求已发出、平台可能已受理 → 第一次就终止，绝不重发。"""
    adapter = _submit_adapter()
    calls = []

    def _fake_post(*a, **k):
        calls.append(1)
        raise requests.ReadTimeout('read timed out')

    monkeypatch.setattr(requests, 'post', _fake_post)
    with pytest.raises(Exception) as exc:
        adapter.submit_checkin({'token': 't'}, 'dorm', 42, None, '', '签到')
    assert len(calls) == 1, f'读超时后重发了 {len(calls)} 次（T5 回归）'
    assert '不重发' in str(exc.value)


def test_submit_connect_error_retries(monkeypatch):
    """连接失败：请求从未抵达平台 → 保留原有的退避重试（3 次）。"""
    adapter = _submit_adapter()
    calls = []

    def _fake_post(*a, **k):
        calls.append(1)
        raise requests.ConnectionError('connection refused')

    monkeypatch.setattr(requests, 'post', _fake_post)
    monkeypatch.setattr('app.services.b_platform.real.time.sleep', lambda s: None)
    with pytest.raises(Exception) as exc:
        adapter.submit_checkin({'token': 't'}, 'dorm', 42, None, '', '签到')
    assert len(calls) == _MAX_NET_RETRIES
    assert '已重试' in str(exc.value)


def test_submit_connect_timeout_retries(monkeypatch):
    """ConnectTimeout 是连接阶段超时（请求未发出），与 ReadTimeout 区别对待——仍可重试。"""
    adapter = _submit_adapter()
    calls = []

    def _fake_post(*a, **k):
        calls.append(1)
        raise requests.ConnectTimeout('connect timed out')

    monkeypatch.setattr(requests, 'post', _fake_post)
    monkeypatch.setattr('app.services.b_platform.real.time.sleep', lambda s: None)
    with pytest.raises(Exception):
        adapter.submit_checkin({'token': 't'}, 'dorm', 42, None, '', '签到')
    assert len(calls) == _MAX_NET_RETRIES


# ==================== T6：窗口展开防重复 ====================

def _mk_schedule_with_window_cfg(app_ctx):
    """course 策略任务（配置口径同 test_activity_windows.jw_env，不含课表 → 窗口清空路径）。
    唯一约束与锁的验证不依赖真实课表：两次展开输出同构行集，重复即撞约束/重复行。"""
    uname = f'tc_wd_{uuid4().hex[:8]}'
    u = User(username=uname, role='user', enabled=True, quota=100, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    acc = BAccount(user_id=u.id, account=f'bp_{uname}', platform='B 打卡平台',
                   type='general', enabled=True)
    acc.set_password('bp-pw')
    db.session.add(acc)
    db.session.flush()
    cs = ConfigSet(user_id=u.id, name='wd测试套', is_default=False)
    cs.set_config({
        'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
                 'weekdays': [1, 2, 3, 4, 5, 6, 7], 'randomDelayMax': 5, 'mode': 'normal'},
        'locationId': None, 'remarks': ['签到'],
        'image': {'enabled': False, 'strategy': 'recycle', 'groupId': ''},
        'push': {'channels': []},
        'advanced': {'uaTemplateId': None, 'customUa': ''},
        'fence': {'intercept': True},
        'activity': {'strategy': 'course',
                     'course': {'leadMinutes': 15, 'tailMinutes': 30,
                                'pollIntervalSec': 120, 'excludeBlocks': []},
                     'fallback': {'enabled': False}},
    })
    db.session.add(cs)
    db.session.flush()
    s = Schedule(user_id=u.id, account_id=acc.id, task_type='activity',
                 mode='standalone', enabled=True, config_set_id=cs.id)
    s.set_config(cs.config)
    db.session.add(s)
    db.session.commit()
    return {'user': u, 'account': acc, 'schedule': s, 'config_set': cs}


def _cleanup_wd(env):
    db.session.rollback()
    ActivityWindow.query.filter_by(schedule_id=env['schedule'].id).delete(synchronize_session=False)
    Schedule.query.filter_by(user_id=env['user'].id).delete(synchronize_session=False)
    ConfigSet.query.filter_by(user_id=env['user'].id).delete(synchronize_session=False)
    BAccount.query.filter_by(user_id=env['user'].id).delete(synchronize_session=False)
    db.session.delete(env['user'])
    db.session.commit()


def test_expanded_windows_respect_unique_constraint(app_ctx, monkeypatch):
    """唯一约束兜底：即便绕过锁同时插两批同键窗口行，数据库也只容得下一行。"""
    env = _mk_schedule_with_window_cfg(app_ctx)
    try:
        now = now_cst()
        row = ActivityWindow(schedule_id=env['schedule'].id, date=now.date(),
                             start_at=now, end_at=now,
                             course_name='上午', sections='1-2', done=False)
        db.session.add(row)
        db.session.commit()

        dup = ActivityWindow(schedule_id=env['schedule'].id, date=now.date(),
                             start_at=now, end_at=now,
                             course_name='上午', sections='1-2', done=False)
        db.session.add(dup)
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()
        rows = ActivityWindow.query.filter_by(schedule_id=env['schedule'].id).all()
        assert len(rows) == 1
    finally:
        _cleanup_wd(env)


def test_concurrent_expands_produce_no_duplicates(app_ctx, monkeypatch):
    """两个线程并发展开同一任务：锁串行化删插事务后，临界区不交叠
    （生产中各线程各持 app context，这里为每线程显式构造）。"""
    env = _mk_schedule_with_window_cfg(app_ctx)
    try:
        from flask import current_app as _flask_app  # 拿当前 app 引用供线程入上下文
        app_ref = _flask_app._get_current_object()

        in_critical = []
        overlap = []

        real_expand = jw_sync.expand_windows_for_schedule

        def _tracking_expand(schedule, today=None):
            in_critical.append(1)
            if len(in_critical) > 1:
                overlap.append(1)  # 已有线程在临界区内又进了一个 → 锁失效
            try:
                return real_expand(schedule, today=today)
            finally:
                in_critical.pop()

        monkeypatch.setattr(jw_sync, 'expand_windows_for_schedule', _tracking_expand)

        def _worker():
            with app_ref.app_context():
                jw_sync.expand_windows_for_schedule_locked(env['schedule'])

        threads = [threading.Thread(target=_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert overlap == [], '锁未生效：多个展开同时处于临界区（T6 回归）'
    finally:
        monkeypatch.undo()
        _cleanup_wd(env)
