# backend/tests/test_scheduler_chain.py
# 模块 D：调度器主链路 —— resolve→前置检查→执行→写记录→状态回写→推送分发
# 用 Stub 适配器（USE_STUB_BPLATFORM=1）验证整条链路，不依赖真机。
# 调度器自动接管在测试环境关闭（conftest 设 SCHEDULER_ENABLED=0），此处显式驱动。
# 读记录/任务状态一律走 HTTP 接口（每次独立事务），规避直写会话的连接可见性差异。
import os

os.environ['USE_STUB_BPLATFORM'] = '1'

import uuid

from app.extensions import db
from app.models import BAccount, ConfigSet, Schedule, SignRecord, User
from app.services import scheduler as sch
from app.services.b_platform.base import BPlatformError, CheckinResult, VerifyResult


def _cfg(weekdays=(1, 2, 3, 4, 5)):
    return {'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
                     'weekdays': list(weekdays), 'randomDelayMax': 5, 'mode': 'normal'},
            'remarks': ['签到'], 'image': {'enabled': False, 'strategy': 'recycle'},
            'push': {}, 'advanced': {'uaTemplateId': None, 'customUa': ''}}


def _uid(c, headers):
    return c.get('/api/auth/me', headers=headers).get_json()['data']['user_id']


def _create_account(c, headers):
    name = f'tc_{uuid.uuid4().hex[:12]}'
    r = c.post('/api/accounts', json={'account': name, 'password': 'x1', 'type': 'dorm'}, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()['data']['id']


def _create_config_set(c, headers, weekdays=(1, 2, 3, 4, 5)):
    r = c.post('/api/config-sets', json={'name': '链路口套', 'config': _cfg(weekdays)}, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()['data']['id']


def _create_schedule(c, headers, acc_id, task_type='dorm'):
    r = c.post('/api/schedules', json={'accountId': acc_id, 'taskType': task_type}, headers=headers)
    assert r.status_code in (200, 201), r.get_json()
    return r.get_json()['data']['id']


def _enable(c, headers, sid, cs_id):
    r = c.put(f'/api/schedules/{sid}', json={'configSetId': cs_id, 'enabled': True}, headers=headers)
    assert r.status_code == 200, r.get_json()
    return r.get_json()['data']


def _records(c, headers, acc_id):
    return c.get(f'/api/accounts/{acc_id}/records', headers=headers).get_json()['data']['items']


def _schedule_dict(c, headers, sid):
    items = c.get('/api/schedules', headers=headers).get_json()['data']['items']
    return next((s for s in items if s['id'] == sid), None)


import pytest


@pytest.fixture(autouse=True)
def _clean_scheduler():
    """每个用例前清空调度器单例的 job，避免跨用例残留干扰。"""
    sch.get_scheduler().remove_all_jobs()
    yield
    sch.get_scheduler().remove_all_jobs()


@pytest.fixture
def chain_user(app_ctx):
    """独立唯一用户，避免与共享 tc_user 的其它测试互相污染 DB 行。"""
    from app.utils.auth import generate_token

    uname = f'tc_chain_{uuid.uuid4().hex[:10]}'
    u = User(username=uname, role='user', enabled=True, quota=100, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    uid = u.id
    yield {'Authorization': f'Bearer {generate_token(u)}'}
    # teardown：清理本用户全部关联数据，杜绝跨测试残留。
    # op_logs 只解外键不删行（审计留痕口径同 purge_user），否则 DELETE users 撞 1451
    from app.models.op_log import OpLog
    OpLog.query.filter_by(user_id=uid).update({'user_id': None}, synchronize_session=False)
    SignRecord.query.filter_by(user_id=uid).delete()
    Schedule.query.filter_by(user_id=uid).delete()
    ConfigSet.query.filter_by(user_id=uid).delete()
    BAccount.query.filter_by(user_id=uid).delete()
    db.session.delete(u)
    db.session.commit()


def test_run_schedule_success_writes_record(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    _enable(c, chain_user, sid, cs_id)

    sch.run_schedule(sid)
    # 刷新连接快照（MySQL REPEATABLE READ + 连接池复用），使后续 HTTP 读可见本次提交
    db.session.commit()

    recs = _records(c, chain_user, acc_id)
    assert any(r['result'] == 'success' for r in recs), recs
    s = _schedule_dict(c, chain_user, sid)
    assert s['lastStatus'] == 'success'
    assert s['runCount'] >= 1
    assert s['nextRunAt']


def test_run_schedule_disabled_account_skips_no_record(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    _enable(c, chain_user, sid, cs_id)
    acc = db.session.get(__import__('app.models', fromlist=['BAccount']).BAccount, acc_id)
    acc.enabled = False
    db.session.commit()

    sch.run_schedule(sid)
    db.session.commit()

    assert _records(c, chain_user, acc_id) == []  # 账号禁用不写记录，避免刷屏
    s = _schedule_dict(c, chain_user, sid)
    assert s['lastStatus'] in (None, 'never')


def test_run_schedule_missing_config_skips(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    # 直接 ORM 置为启用但无配置套（绕过路由开启校验，专测 resolve 缺失分支）
    s = db.session.get(Schedule, sid)
    s.enabled = True
    s.config_set_id = None
    s.mode = 'follow'
    db.session.commit()

    sch.run_schedule(sid)
    db.session.commit()

    recs = _records(c, chain_user, acc_id)
    assert any(r['result'] == 'skip' for r in recs), recs
    assert '配置缺失' in (recs[0]['failReason'] or '')


def test_run_schedule_checkin_error_writes_fail(app, chain_user, monkeypatch):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    _enable(c, chain_user, sid, cs_id)

    class FailAdapter:
        name = 'fail'

        def verify_and_fetch(self, *a, **k):
            return VerifyResult(ok=True, token='t', bp_uid=1, profile={})

        def find_active_task(self, session, task_type):
            return {'task': {'id': 1, 'taskName': '失败任务', 'needPhoto': False,
                             'startTime': '00:00:00', 'endTime': '23:59:59'},
                    'fence': []}

        def submit_checkin(self, *a, **k):
            raise BPlatformError('network', '断网了')

    monkeypatch.setattr(sch, 'get_adapter', lambda: FailAdapter())

    sch.run_schedule(sid)
    db.session.commit()

    recs = _records(c, chain_user, acc_id)
    assert any(r['result'] == 'fail' for r in recs), recs
    assert 'B 平台错误' in (recs[0]['failReason'] or '')


def test_sync_schedule_register_and_remove(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    jid = sch._job_id(sid)

    _enable(c, chain_user, sid, cs_id)
    assert sch.get_scheduler().get_job(jid) is not None

    c.put(f'/api/schedules/{sid}', json={'enabled': False}, headers=chain_user)
    assert sch.get_scheduler().get_job(jid) is None


def test_reconcile_removes_orphan_and_registers_missing(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    sid2 = _create_schedule(c, chain_user, acc_id, task_type='activity')
    jid = sch._job_id(sid)

    # 经路由启用 → 事件钩子注册 job
    _enable(c, chain_user, sid, cs_id)
    assert sch.get_scheduler().get_job(jid) is not None

    # 模拟孤儿：直接删 Schedule 行（如账号级联删除绕过路由）
    orphan = db.session.get(Schedule, sid)
    db.session.delete(orphan)
    db.session.commit()
    sch.reconcile()
    assert sch.get_scheduler().get_job(jid) is None

    # 另一条启用任务经 ORM 直接建立（错过事件钩子）→ 对账补注册
    s2 = db.session.get(Schedule, sid2)
    s2.enabled = True
    s2.config_set_id = cs_id
    s2.mode = 'follow'
    db.session.commit()
    sch.reconcile()
    assert sch.get_scheduler().get_job(sch._job_id(sid2)) is not None


def test_reconcile_missed_runs_same_day_only(app, chain_user, monkeypatch):
    """启动对账同日判定：计划时刻在当天 → 安排补跑；计划时刻在昨天及更早 →
    不补跑，落 skip 说明且 next_run_at 推进到未来（两类签到任务都只当天有效，
    补跑几天前的计划只会产出必然失败的噪音）。"""
    from datetime import timedelta

    from app.models.user import now_cst

    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid_today = _create_schedule(c, chain_user, acc_id)
    sid_stale = _create_schedule(c, chain_user, acc_id, task_type='activity')
    _enable(c, chain_user, sid_today, cs_id)
    # activity 任务与 dorm 配置套类型不符，路由会拒绝；照 register_all_enabled
    # 用例的口径直接 ORM 建立关联（对账逻辑不关心配置套类型）
    s_stale_row = db.session.get(Schedule, sid_stale)
    s_stale_row.enabled = True
    s_stale_row.config_set_id = cs_id
    s_stale_row.mode = 'follow'
    db.session.commit()

    now = now_cst()
    with app.app_context():
        # 当天 02:00（已过时刻，但在当天）→ 补跑
        db.session.get(Schedule, sid_today).next_run_at = now.replace(
            hour=2, minute=0, second=0, microsecond=0)
        # 昨天 21:20 → 跨天，不补跑
        db.session.get(Schedule, sid_stale).next_run_at = (
            now - timedelta(days=1)).replace(hour=21, minute=20, second=0, microsecond=0)
        db.session.commit()

    pushed = []
    monkeypatch.setattr(sch, '_push_outcome',
                        lambda *a, **k: pushed.append((a[3], a[4])))
    sch._reconcile_missed_runs()

    # 当天：有补跑 job；跨天：无 job
    assert sch.get_scheduler().get_job(f'_reconcile_{sid_today}') is not None
    assert sch.get_scheduler().get_job(f'_reconcile_{sid_stale}') is None

    # 跨天任务：next_run_at 已推进到未来 + 落了一条 skip 记录
    with app.app_context():
        s_stale = db.session.get(Schedule, sid_stale)
        assert s_stale.next_run_at > now_cst()
        rec = (SignRecord.query.filter_by(schedule_id=sid_stale, status='skip')
               .order_by(SignRecord.id.desc()).first())
        assert rec is not None
        assert '跨天' in (rec.fail_reason or '')
    # skip 说明照常推送（notify.skip 开关裁决在 dispatch_push 内）
    assert any(status == 'skip' and '跨天' in reason for status, reason in pushed), pushed

    # 清理补跑 job，避免污染后续用例（_clean_scheduler 亦兜底）
    sch.get_scheduler().remove_all_jobs()


def test_register_all_enabled(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid1 = _create_schedule(c, chain_user, acc_id)
    sid2 = _create_schedule(c, chain_user, acc_id, task_type='activity')
    for sid in (sid1, sid2):
        s = db.session.get(Schedule, sid)
        s.enabled = True
        s.config_set_id = cs_id
        s.mode = 'follow'
    db.session.commit()

    sch.register_all_enabled()

    assert sch.get_scheduler().get_job(sch._job_id(sid1)) is not None
    assert sch.get_scheduler().get_job(sch._job_id(sid2)) is not None


def test_register_job_applies_random_delay_jitter(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user, weekdays=(1,))  # randomDelayMax=5（见 _cfg）
    sid = _create_schedule(c, chain_user, acc_id)
    s = db.session.get(Schedule, sid)
    s.enabled = True
    s.config_set_id = cs_id
    s.mode = 'follow'
    db.session.commit()

    sch._register_job(s)
    job = sch.get_scheduler().get_job(sch._job_id(sid))
    assert job is not None
    # CronTrigger.jitter 单位为秒；randomDelayMax=5 分钟 → 300 秒
    assert job.trigger.jitter == 300


def test_register_job_no_jitter_when_delay_zero(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user, weekdays=(1,))
    # 把配置套 randomDelayMax 改 0（config 是只读 property，必须用 set_config）
    cs = db.session.get(ConfigSet, cs_id)
    cfg = dict(cs.config)
    cfg['time'] = dict(cfg['time'])
    cfg['time']['randomDelayMax'] = 0
    cs.set_config(cfg)
    db.session.commit()
    sid = _create_schedule(c, chain_user, acc_id)
    s = db.session.get(Schedule, sid)
    s.enabled = True
    s.config_set_id = cs_id
    s.mode = 'follow'
    db.session.commit()

    sch._register_job(s)
    job = sch.get_scheduler().get_job(sch._job_id(sid))
    assert job is not None
    assert job.trigger.jitter is None


def test_resolve_merges_overrides(app, chain_user):
    """follow 模式 = 配置套 + 覆盖浅合并：覆盖键生效，未覆盖键继续跟随配置套；
    执行时刻解析（注册/展示共用）同口径应用覆盖。"""
    from app.utils.schedule_utils import extract_schedule_time

    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)  # 08:00，randomDelayMax=5，remarks=['签到']
    sid = _create_schedule(c, chain_user, acc_id)
    _enable(c, chain_user, sid, cs_id)
    ov = {'time': {'signTime': {'hour': 7, 'minute': 30}, 'startHour': 8, 'endHour': 22,
                   'weekdays': [1], 'randomDelayMax': 2, 'mode': 'normal'}}
    r = c.put(f'/api/schedules/{sid}', json={'overrides': ov}, headers=chain_user)
    assert r.status_code == 200, r.get_json()

    with app.app_context():
        s = db.session.get(Schedule, sid)
        merged = sch._resolve(s)
    assert merged['time']['signTime']['hour'] == 7      # 覆盖生效
    assert merged['remarks'] == ['签到']                # 未覆盖键继续跟随配置套

    hour, minute, weekdays = extract_schedule_time(db.session.get(Schedule, sid))
    assert (hour, minute, weekdays) == (7, 30, [1])


class _PushRecorder:
    """捕获 _push_outcome → dispatch_push 的调用参数（status/reason），不真发请求。"""
    calls = []

    @classmethod
    def record(cls, resolved, schedule, acc, status, reason='', **kw):
        cls.calls.append({'status': status, 'reason': reason})


def _push_cfg():
    """带推送通道的配置（直接填写 serverchan），notify 三态全开。"""
    cfg = _cfg()
    cfg['push'] = {'channels': ['serverchan'], 'useOwnCredential': False,
                   'credIds': {}, 'cred': {'serverchanKey': 'SCTx'},
                   'notify': {'success': True, 'skip': True, 'fail': True}}
    return cfg


@pytest.fixture()
def _record_push(monkeypatch):
    _PushRecorder.calls = []
    monkeypatch.setattr(sch, 'dispatch_push', _PushRecorder.record)
    return _PushRecorder


def test_run_schedule_platform_error_pushes_fail(app, chain_user, _record_push):
    """回归：BPlatformError 异常路径（如验证码超时）此前只落库不推送，
    失败通知被静默吞掉——现在异常失败同样分发推送（notify.fail 裁决）。"""
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    _enable(c, chain_user, sid, cs_id)

    class TimeoutAdapter:
        name = 'timeout'

        def verify_and_fetch(self, *a, **k):
            return VerifyResult(ok=True, token='t', bp_uid=1, profile={})

        def find_active_task(self, session, task_type):
            raise BPlatformError('network', '获取验证码失败：Read timed out')

    from pytest import MonkeyPatch
    mp = MonkeyPatch()
    mp.setattr(sch, 'get_adapter', lambda: TimeoutAdapter())
    try:
        # 网络失败会安排补跑 job，测试结束清掉（_clean_scheduler 亦兜底）
        sch.run_schedule(sid)
    finally:
        mp.undo()
    db.session.commit()

    assert len(_PushRecorder.calls) == 1, _PushRecorder.calls
    call = _PushRecorder.calls[0]
    assert call['status'] == 'fail'
    assert 'B 平台错误' in call['reason']

    recs = _records(c, chain_user, acc_id)
    assert any(r['result'] == 'fail' for r in recs), recs


def test_run_schedule_unexpected_error_pushes_fail(app, chain_user, _record_push):
    """未预期异常（非 BPlatformError）同样落库 + 推送，两条路径口径一致。"""
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    _enable(c, chain_user, sid, cs_id)

    class BoomAdapter:
        name = 'boom'

        def verify_and_fetch(self, *a, **k):
            return VerifyResult(ok=True, token='t', bp_uid=1, profile={})

        def find_active_task(self, session, task_type):
            raise ValueError('意外错误')

    from pytest import MonkeyPatch
    mp = MonkeyPatch()
    mp.setattr(sch, 'get_adapter', lambda: BoomAdapter())
    try:
        sch.run_schedule(sid)
    finally:
        mp.undo()
    db.session.commit()

    assert len(_PushRecorder.calls) == 1, _PushRecorder.calls
    assert _PushRecorder.calls[0]['status'] == 'fail'
    assert '执行异常' in _PushRecorder.calls[0]['reason']


def test_run_schedule_notify_fail_off_skips_push(app, chain_user, monkeypatch):
    """notify.fail 关闭时异常失败不发推送——开关语义在 dispatch_push 内裁决，
    故此处 mock requests.post 断言无网络请求（而非 mock dispatch_push 本身）。"""
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    _enable(c, chain_user, sid, cs_id)

    # 把配置套 push 的 notify.fail 关掉
    with app.app_context():
        cs_row = db.session.get(ConfigSet, cs_id)
        cfg = cs_row.config
        cfg['push'] = {'channels': ['serverchan'], 'useOwnCredential': False,
                       'credIds': {}, 'cred': {'serverchanKey': 'SCTx'},
                       'notify': {'success': True, 'skip': True, 'fail': False}}
        cs_row.set_config(cfg)
        db.session.commit()

    http_calls = []

    def fake_post(url, **kw):
        http_calls.append(url)
        return type('R', (), {'status_code': 200,
                              'json': lambda self: {'code': 0, 'message': ''}})()

    monkeypatch.setattr(sch.requests, 'post', fake_post)

    class TimeoutAdapter:
        name = 'timeout'

        def verify_and_fetch(self, *a, **k):
            return VerifyResult(ok=True, token='t', bp_uid=1, profile={})

        def find_active_task(self, session, task_type):
            raise BPlatformError('network', '断网')

    monkeypatch.setattr(sch, 'get_adapter', lambda: TimeoutAdapter())
    sch.run_schedule(sid)
    db.session.commit()

    assert http_calls == [], http_calls  # notify.fail 关闭：无任何推送请求发出
    recs = _records(c, chain_user, acc_id)
    assert any(r['result'] == 'fail' for r in recs), recs  # 失败记录仍正常落库
