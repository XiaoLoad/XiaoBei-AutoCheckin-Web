# 审计 T7/T8 回归：
# T7——群合并推送「延迟 job + 30s 对账」双保险同刻触发时，原实现各自查 log 无记录后
#     都发 send_qq（唯一约束只兜落库、兜不住已发出的网络推送）→ QQ 群收到两条相同汇总。
#     现行为：发送前 DELETE pending 行原子认领（谁删到谁发），行被删走的一方直接退出；
#     发送失败按 attempts 线性退避重排队（1/2/3/4 分钟），超限记 fail 终态不再重试。
# T8——批量接口原实现循环内先 sync_schedule（注册调度 job，停用分支内部还有 commit）
#     最后才 commit：commit 失败留孤儿 job、中途异常把前半批未提交改动隐式提交。
#     现行为：循环只改 session，commit 成功后再统一 sync；targets 超过 200 直接 400；
#     add_members 改批量查询（2 次查询替代逐条 2N 次），重复/无效 id 静默跳过。
import os

os.environ['USE_STUB_BPLATFORM'] = '1'

import uuid
from datetime import date, timedelta

from app.extensions import db
from app.models import (BAccount, PushGroup, PushGroupDigestLog, PushGroupDigestPending,
                        PushGroupMember)
from app.models.user import now_cst
from app.services import group_digest as gd
from app.services.crypto import encrypt
from app.models.pools import PoolCredential

D = date(2026, 10, 5)


# ───────────────────────── 工具 ─────────────────────────

def _env(app_ctx):
    """唯一用户 + 绑定 QQ 群的 dorm 分组 + pushplus-open 凭证，yield (uid, group)。"""
    uname = f'tc_t7t8_{uuid.uuid4().hex[:10]}'
    from app.models import User
    u = User(username=uname, role='user', enabled=True, quota=100, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    g = PushGroup(user_id=u.id, type=PushGroup.TYPE_DORM, name='507', qq_code='grp-507')
    db.session.add(g)
    db.session.add(PoolCredential(user_id=u.id, channel='pushplus-open', name='t',
                                  secret_enc=encrypt('{"token": "OPEN-TOKEN"}'), enabled=True))
    db.session.commit()
    return u.id, g


def _cleanup(uid):
    gids = [g.id for g in PushGroup.query.filter_by(user_id=uid).all()]
    if gids:
        PushGroupDigestPending.query.filter(PushGroupDigestPending.group_id.in_(gids)) \
            .delete(synchronize_session=False)
        PushGroupDigestLog.query.filter(PushGroupDigestLog.group_id.in_(gids)) \
            .delete(synchronize_session=False)
        PushGroupMember.query.filter(PushGroupMember.group_id.in_(gids)) \
            .delete(synchronize_session=False)
        PushGroup.query.filter(PushGroup.id.in_(gids)).delete(synchronize_session=False)
    PoolCredential.query.filter_by(user_id=uid).delete(synchronize_session=False)
    BAccount.query.filter_by(user_id=uid).delete(synchronize_session=False)
    db.session.delete(db.session.get(type(PushGroup.query.filter_by(user_id=uid).first()),
                                     0) if False else _user(uid))
    db.session.commit()


def _user(uid):
    from app.models import User
    return db.session.get(User, uid)


def _pending(group_id, date=D, attempts=0, flush_at=None):
    db.session.add(PushGroupDigestPending(
        group_id=group_id, date=date,
        flush_at=flush_at or (now_cst() - timedelta(minutes=1)), attempts=attempts))
    db.session.commit()


def _fail_send(monkeypatch):
    """拦截 send_qq 返回失败；记录调用次数。"""
    calls = {'n': 0}

    def fake_send_qq(token, qq_code, title, content, template='markdown'):
        calls['n'] += 1
        return False, '模拟平台拒绝'

    monkeypatch.setattr(gd, 'send_qq', fake_send_qq)
    return calls


# ───────────────────────── T7：原子认领 ─────────────────────────

def test_t7_claim_prevents_double_send(app_ctx, monkeypatch):
    """双保险同刻触发：延迟 job 先认领删除 pending 行后，对账方查行不存在必须退出，
    send_qq 全程只被调用一次——重复推送在结构上不可能。"""
    uid, g = _env(app_ctx)
    try:
        _pending(g.id)
        calls = _fail_send(monkeypatch)  # 发送失败也不影响断言：两次失败推送同样是重复推送

        gd.flush_digest(g.id, D)     # 延迟 job：认领成功，执行发送（失败 → 重排队）
        gd.flush_digest(g.id, D)     # 对账兜底：行已删走，必须直接退出

        # 认领成功方跑完发送；认领失败方未触碰 send_qq
        assert calls['n'] == 1, '同一组同一天只允许一次网络推送'
        # 发送失败已重排队（attempts=1，约 1 分钟后对账重试）
        row = PushGroupDigestPending.query.filter_by(group_id=g.id, date=D).first()
        assert row is not None and row.attempts == 1
    finally:
        _cleanup(uid)


def test_t7_no_pending_row_returns_and_sends_nothing(app_ctx, monkeypatch):
    """pending 行不存在（已被处理）时 flush 非 force 调用直接退出，不发请求不写日志。"""
    uid, g = _env(app_ctx)
    try:
        calls = _fail_send(monkeypatch)
        gd.flush_digest(g.id, D)  # 无 pending 行：非 force 直接退出
        assert calls['n'] == 0
        assert PushGroupDigestLog.query.filter_by(group_id=g.id, date=D).first() is None
    finally:
        _cleanup(uid)


def test_t7_force_flush_skips_claim(app_ctx, monkeypatch):
    """手动补发（force=True）跳过认领直接发送，不要求 pending 行存在。"""
    uid, g = _env(app_ctx)
    try:
        sent = {}
        monkeypatch.setattr(gd, 'send_qq',
                            lambda token, qq_code, title, content, template='markdown':
                            sent.update(qq=qq_code) or (True, ''))
        gd.flush_digest(g.id, D, force=True)
        assert sent.get('qq') == 'grp-507'
        log = PushGroupDigestLog.query.filter_by(group_id=g.id, date=D).first()
        assert log is not None and log.status == PushGroupDigestLog.STATUS_SUCCESS
    finally:
        _cleanup(uid)


def test_t7_failed_send_requeues_with_backoff(app_ctx, monkeypatch):
    """发送失败重排队：flush_at 顺延 attempts 分钟，attempts 累计；成功后行被清理。"""
    uid, g = _env(app_ctx)
    try:
        _pending(g.id)
        calls = _fail_send(monkeypatch)

        gd.flush_digest(g.id, D)
        row1 = PushGroupDigestPending.query.filter_by(group_id=g.id, date=D).first()
        assert row1.attempts == 1 and calls['n'] == 1

        # 把 flush_at 拨回过去模拟到点，再失败一次：attempts=2
        row1.flush_at = now_cst() - timedelta(minutes=1)
        db.session.commit()
        gd.flush_digest(g.id, D)
        row2 = PushGroupDigestPending.query.filter_by(group_id=g.id, date=D).first()
        assert row2.attempts == 2 and calls['n'] == 2

        # 第三次成功：pending 清空，审计落 success
        row2.flush_at = now_cst() - timedelta(minutes=1)
        db.session.commit()
        monkeypatch.setattr(gd, 'send_qq',
                            lambda token, qq_code, title, content, template='markdown': (True, ''))
        gd.flush_digest(g.id, D)
        assert PushGroupDigestPending.query.filter_by(group_id=g.id, date=D).first() is None
        log = PushGroupDigestLog.query.filter_by(group_id=g.id, date=D).first()
        assert log.status == PushGroupDigestLog.STATUS_SUCCESS
    finally:
        _cleanup(uid)


def test_t7_attempts_exhausted_writes_fail_log(app_ctx, monkeypatch):
    """重试达 MAX_FLUSH_ATTEMPTS 上限：记 fail 终态（message 带重试次数），不再重排队。"""
    uid, g = _env(app_ctx)
    try:
        _pending(g.id, attempts=gd.MAX_FLUSH_ATTEMPTS - 1)  # 上一次已试到 4
        calls = _fail_send(monkeypatch)

        gd.flush_digest(g.id, D)  # 第 5 次失败 → 触顶
        assert calls['n'] == 1
        assert PushGroupDigestPending.query.filter_by(group_id=g.id, date=D).first() is None
        log = PushGroupDigestLog.query.filter_by(group_id=g.id, date=D).first()
        assert log is not None and log.status == PushGroupDigestLog.STATUS_FAIL
        assert f'重试 {gd.MAX_FLUSH_ATTEMPTS}' in log.message
    finally:
        _cleanup(uid)


def test_t7_reconcile_respects_claim(app_ctx, monkeypatch):
    """对账入口：pending 未到点不动；到点后走 flush（认领语义自动生效）。"""
    uid, g = _env(app_ctx)
    try:
        _pending(g.id, flush_at=now_cst() + timedelta(hours=1))  # 未到点
        gd.reconcile_pending_digests()
        assert PushGroupDigestPending.query.filter_by(group_id=g.id, date=D).first() is not None

        calls = _fail_send(monkeypatch)
        row = PushGroupDigestPending.query.filter_by(group_id=g.id, date=D).first()
        row.flush_at = now_cst() - timedelta(minutes=1)
        db.session.commit()
        gd.reconcile_pending_digests()
        assert calls['n'] == 1  # 到点 → 认领 → 发送（失败重排队）
    finally:
        _cleanup(uid)


# ───────────────────────── T8：批量接口 ─────────────────────────

def _create_account(c, headers):
    name = f'tc_{uuid.uuid4().hex[:12]}'
    r = c.post('/api/accounts', json={'account': name, 'password': 'x1', 'type': 'dorm'},
               headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()['data']['id']


def _create_set(c, headers, name='T8套'):
    cfg = {'time': {'signTime': {'hour': 8, 'minute': 30},
                    'startHour': 8, 'endHour': 22, 'weekdays': [1, 2, 3, 4, 5, 6, 7],
                    'randomDelayMax': 5, 'mode': 'normal'},
           'remarks': ['签到'], 'image': {'enabled': False, 'strategy': 'recycle'},
           'push': {'channels': [], 'useOwnCredential': True, 'credIds': {}, 'cred': {}, 'notify': {}},
           'advanced': {'uaTemplateId': None, 'customUa': ''}}
    r = c.post('/api/config-sets', json={'name': name, 'config': cfg}, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()['data']['id']


def test_t8_batch_manage_rejects_oversized_targets(app, user_headers):
    """targets 超过 200 直接 400：防超大批量构造单请求长事务锁表。"""
    c = app.test_client()
    targets = [{'accountId': i, 'taskType': 'dorm'} for i in range(201)]
    r = c.post('/api/schedules/batch-manage',
               json={'action': 'disable', 'targets': targets}, headers=user_headers)
    assert r.status_code == 400
    assert r.get_json()['code'] == 4402


def test_t8_apply_batch_rejects_oversized_targets(app, user_headers):
    c = app.test_client()
    targets = [{'accountId': i, 'taskType': 'dorm'} for i in range(201)]
    r = c.post('/api/config-sets/99999/apply-batch',
               json={'targets': targets}, headers=user_headers)
    assert r.status_code == 400
    assert r.get_json()['code'] == 4402


def test_t8_batch_manage_syncs_after_commit(app, user_headers, monkeypatch):
    """batch_manage 的 sync_schedule 必须在 commit 成功之后才调用（顺序回归）。"""
    from app.routes import schedules as schedules_route
    c = app.test_client()
    acc_id = None
    try:
        acc_id = _create_account(c, user_headers)
        sched_id = c.post('/api/schedules', json={'accountId': acc_id, 'taskType': 'dorm'},
                          headers=user_headers).get_json()['data']['id']

        order = []
        real_commit = db.session.commit

        def spy_commit():
            order.append('commit')
            real_commit()

        def spy_sync(sc):
            order.append('sync')

        monkeypatch.setattr(db.session, 'commit', spy_commit)
        monkeypatch.setattr(schedules_route, 'sync_schedule', spy_sync)

        r = c.post('/api/schedules/batch-manage',
                   json={'action': 'disable', 'targets': [{'accountId': acc_id, 'taskType': 'dorm'}]},
                   headers=user_headers)
        assert r.status_code == 200, r.get_json()
        assert 'sync' not in order or order.index('commit') < order.index('sync'), \
            f'sync 必须晚于 commit，实际顺序 {order}'
    finally:
        if acc_id:
            c.delete(f'/api/accounts/{acc_id}', headers=user_headers)


def test_t8_add_members_batch_queries(app, user_headers):
    """add_members：重复 id、不存在 id、他人 id 均静默跳过；有效 id 一次性入组。"""
    c = app.test_client()
    acc_id = None
    other_acc = None
    try:
        acc_id = _create_account(c, user_headers)
        g = c.post('/api/group-push/groups', json={'name': f'507-{uuid.uuid4().hex[:6]}'},
                   headers=user_headers).get_json()['data']

        # 重复 id 只加一次
        r = c.post(f'/api/group-push/groups/{g["id"]}/members',
                   json={'accountIds': [acc_id, acc_id, 'abc', 99999999]},
                   headers=user_headers)
        assert r.status_code == 200, r.get_json()
        assert r.get_json()['data']['added'] == 1

        # 二次添加同一账号：已是成员，added=0
        r = c.post(f'/api/group-push/groups/{g["id"]}/members',
                   json={'accountIds': [acc_id]}, headers=user_headers)
        assert r.get_json()['data']['added'] == 0

        members = PushGroupMember.query.filter_by(group_id=g['id']).all()
        assert [m.account_id for m in members] == [acc_id]
    finally:
        if acc_id:
            c.delete(f'/api/accounts/{acc_id}', headers=user_headers)


def test_t8_add_members_rejects_oversized_ids(app, user_headers):
    c = app.test_client()
    r = c.post('/api/group-push/groups/1/members',
               json={'accountIds': list(range(201))}, headers=user_headers)
    assert r.status_code == 400
