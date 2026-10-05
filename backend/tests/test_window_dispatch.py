# T4 回归：活动窗口命中后异步派发签到链路，30s 心跳不再被完整链路绑死
#
# reconcile 是 30s interval job 且 max_instances=1：旧实现在心跳线程内就地执行
# run_schedule（登录/定位/提交/推送，最坏数分钟），期间孤儿清理、状态对账、
# 群推送补发全部顺延。修复后心跳只做轻量对账 + add_job 派发。
# 两条路径均覆盖：正常命中活动（w.done=True 后派发）与轮询遇凭证失效转链路。
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.extensions import db
from app.models import ActivityWindow, BAccount, ConfigSet, Schedule, User
from app.services import scheduler as sch
from app.services.b_platform.base import BPlatformError
from app.models.user import now_cst

# 最小活动 course 配置（口径对齐 test_activity_windows.jw_env）：
# resolve_activity_cfg 需要识别为 course 策略，轮询间隔 120s
_ACTIVITY_CONFIG = {
    'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
             'weekdays': [1, 2, 3, 4, 5, 6, 7], 'randomDelayMax': 5, 'mode': 'normal'},
    'locationId': None,
    'remarks': ['测试备注'],
    'image': {'enabled': False, 'strategy': 'recycle', 'groupId': ''},
    'push': {'channels': []},
    'advanced': {'uaTemplateId': None, 'customUa': ''},
    'fence': {'intercept': True},
    'activity': {'strategy': 'course', 'course': {'leadMinutes': 15, 'tailMinutes': 30,
                                                  'pollIntervalSec': 120,
                                                  'excludeBlocks': []},
                 'fallback': {'enabled': False}},
}


def _mk_window_env(app_ctx):
    """最小窗口环境：用户 + 启用的活动 course 任务（带配置）+ 当天开着的未完结窗口。"""
    uname = f'tc_win_{uuid4().hex[:8]}'
    u = User(username=uname, role='user', enabled=True, quota=100, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    acc = BAccount(user_id=u.id, account=f'bp_{uname}', platform='B 打卡平台',
                   type='general', enabled=True)
    acc.set_password('bp-pw')
    db.session.add(acc)
    db.session.flush()
    cs = ConfigSet(user_id=u.id, name='win测试套', is_default=False)
    cs.set_config(_ACTIVITY_CONFIG)
    db.session.add(cs)
    db.session.flush()
    s = Schedule(user_id=u.id, account_id=acc.id, task_type='activity',
                 mode='standalone', enabled=True, config_set_id=cs.id)
    s.set_config(cs.config)
    db.session.add(s)
    db.session.flush()
    now = now_cst()
    w = ActivityWindow(schedule_id=s.id, course_name='测试课程',
                       date=now.date(),
                       start_at=now - timedelta(minutes=10),
                       end_at=now + timedelta(minutes=50),
                       done=False, last_polled_at=None)
    db.session.add(w)
    db.session.commit()
    return {'user': u, 'account': acc, 'schedule': s, 'window': w, 'config_set': cs}


def _cleanup(env):
    db.session.rollback()
    sch.get_scheduler().remove_all_jobs()
    ActivityWindow.query.filter_by(schedule_id=env['schedule'].id).delete(synchronize_session=False)
    Schedule.query.filter_by(user_id=env['user'].id).delete(synchronize_session=False)
    ConfigSet.query.filter_by(user_id=env['user'].id).delete(synchronize_session=False)
    BAccount.query.filter_by(user_id=env['user'].id).delete(synchronize_session=False)
    db.session.delete(env['user'])
    db.session.commit()


def _dispatch_jobs(env):
    return [j for j in sch.get_scheduler().get_jobs()
            if j.id.startswith(f"dispatch_{env['schedule'].id}_")]


def test_window_hit_dispatches_instead_of_inline_run(app_ctx, monkeypatch):
    """命中活动 → run_schedule 不得在心跳线程内就地执行，须派发为独立 job。"""
    env = _mk_window_env(app_ctx)
    try:
        inline_calls = []

        def _fail_inline(schedule_id, **kw):
            inline_calls.append(schedule_id)
            raise AssertionError('run_schedule 被心跳线程就地调用了（T4 回归）')

        def _fake_find_active_task(session, kind):
            return {'task': {'id': 77, 'name': '测试活动'}}

        monkeypatch.setattr(sch, 'run_schedule', _fail_inline)
        monkeypatch.setattr(sch, 'get_adapter',
                            lambda: SimpleNamespace(find_active_task=_fake_find_active_task))

        sch._poll_activity_windows()

        assert inline_calls == []
        assert db.session.get(ActivityWindow, env['window'].id).done is True
        # 派发 job 已注册到线程池（幂等 id 带毫秒时间戳，仅此一条）
        assert len(_dispatch_jobs(env)) == 1
    finally:
        monkeypatch.undo()
        _cleanup(env)


def test_credential_error_dispatches_full_chain(app_ctx, monkeypatch):
    """轮询遇凭证失效 → 窗口转正并派发完整链路（内部自会重登），心跳线程不被阻塞。"""
    env = _mk_window_env(app_ctx)
    try:
        def _fake_find_active_task(session, kind):
            raise BPlatformError('credential', '凭证失效')

        monkeypatch.setattr(sch, 'get_adapter',
                            lambda: SimpleNamespace(find_active_task=_fake_find_active_task))
        monkeypatch.setattr(sch, 'run_schedule',
                            lambda *a, **k: (_ for _ in ()).throw(
                                AssertionError('run_schedule 被心跳线程就地调用了（T4 回归）')))

        sch._poll_activity_windows()

        assert db.session.get(ActivityWindow, env['window'].id).done is True
        assert len(_dispatch_jobs(env)) == 1
    finally:
        monkeypatch.undo()
        _cleanup(env)


def test_dispatch_failure_keeps_window_done(app_ctx, monkeypatch):
    """派发异常仅记日志：窗口已标记完结，不因 add_job 失败回滚重复派发。"""
    env = _mk_window_env(app_ctx)
    try:
        def _fake_find_active_task(session, kind):
            return {'task': {'id': 77, 'name': '测试活动'}}

        monkeypatch.setattr(sch, 'get_adapter',
                            lambda: SimpleNamespace(find_active_task=_fake_find_active_task))

        def _boom(*a, **k):
            raise RuntimeError('调度器不可用')

        monkeypatch.setattr(sch, 'get_scheduler', _boom)
        sch._poll_activity_windows()

        assert db.session.get(ActivityWindow, env['window'].id).done is True
    finally:
        monkeypatch.undo()
        _cleanup(env)
