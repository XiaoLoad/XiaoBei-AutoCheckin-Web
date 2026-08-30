# 推送分发单测：验证 dispatch_push 能正确解析配置套 push 结构
# （直接填写 / 资源池凭证两种来源）、按 notify 开关分发、覆盖 serverchan / pushplus。
import json

import pytest

import app.services.scheduler as sch
from app.services.crypto import encrypt
from app.models.pools import PoolCredential
from app.models.user import User


@pytest.fixture(autouse=True)
def _clean_creds(app_ctx):
    yield
    sch.db.session.query(PoolCredential).filter_by(user_id=_uid(sch.db)).delete()
    sch.db.session.commit()


class _FakeSchedule:
    def __init__(self, user_id, task_type='dorm'):
        self.id = 0
        self.user_id = user_id
        self.task_type = task_type


class _FakeAcc:
    account = 'tc_push_acc'


def _make_cred(db, user_id, channel, fields):
    c = PoolCredential(user_id=user_id, channel=channel, name='t',
                       secret_enc=encrypt(json.dumps(fields, ensure_ascii=False)),
                       enabled=True)
    db.session.add(c)
    db.session.commit()
    return c.id


def _capture(monkeypatch, body=None):
    """伪造 requests.post：默认返回各通道业务成功码；body 可覆盖以模拟平台拒绝。
    HTTP 层通不代表送达——业务码校验依赖响应体，fake 须提供 json()。"""
    calls = []

    def fake_post(url, **kw):
        calls.append((url, kw))
        if body is None:
            payload = {'code': 200, 'msg': 'ok'} if 'pushplus' in url else {'code': 0, 'message': ''}
        else:
            payload = body
        return type('R', (), {'status_code': 200, 'json': lambda self: payload})()

    monkeypatch.setattr(sch.requests, 'post', fake_post)
    return calls


def _uid(db):
    u = User.query.filter_by(username='tc_push_user').first()
    if u is None:
        u = User(username='tc_push_user', role='user', enabled=True, quota=10, used_quota=0)
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
    return u.id


def test_dispatch_resolves_pool_credential_serverchan(app_ctx, monkeypatch):
    db = sch.db
    uid = _uid(db)
    cid = _make_cred(db, uid, 'serverchan', {'serverchanKey': 'SCTxyz'})

    calls = _capture(monkeypatch)
    resolved = {'push': {
        'channels': ['serverchan'],
        'useOwnCredential': True,
        'credIds': {'serverchan': cid, 'pushplus': None, 'email': None},
        'cred': {},
        'notify': {'success': True, 'skip': False, 'fail': False},
    }}
    sch.dispatch_push(resolved, _FakeSchedule(uid), _FakeAcc(), 'success')

    assert len(calls) == 1
    assert calls[0][0] == 'https://sctapi.ftqq.com/SCTxyz.send'


def test_dispatch_resolves_direct_fill_pushplus(app_ctx, monkeypatch):
    db = sch.db
    uid = _uid(db)

    calls = _capture(monkeypatch)
    resolved = {'push': {
        'channels': ['pushplus'],
        'useOwnCredential': False,
        'credIds': {'serverchan': None, 'pushplus': None, 'email': None},
        'cred': {'pushplusToken': 'PPTok'},
        'notify': {'success': True, 'skip': False, 'fail': False},
    }}
    sch.dispatch_push(resolved, _FakeSchedule(uid), _FakeAcc(), 'success')

    assert len(calls) == 1
    assert calls[0][0] == 'https://www.pushplus.plus/send'
    assert calls[0][1]['json']['token'] == 'PPTok'


def test_dispatch_respects_notify_success_off(app_ctx, monkeypatch):
    db = sch.db
    uid = _uid(db)
    cid = _make_cred(db, uid, 'serverchan', {'serverchanKey': 'SCTxyz'})

    calls = _capture(monkeypatch)
    resolved = {'push': {
        'channels': ['serverchan'],
        'useOwnCredential': True,
        'credIds': {'serverchan': cid, 'pushplus': None, 'email': None},
        'cred': {},
        'notify': {'success': False, 'skip': True, 'fail': True},  # 成功关闭
    }}
    sch.dispatch_push(resolved, _FakeSchedule(uid), _FakeAcc(), 'success')

    assert calls == []  # 成功开关关闭，不发


def test_dispatch_skip_fires_when_notify_skip_on(app_ctx, monkeypatch):
    db = sch.db
    uid = _uid(db)
    cid = _make_cred(db, uid, 'serverchan', {'serverchanKey': 'SCTxyz'})

    calls = _capture(monkeypatch)
    resolved = {'push': {
        'channels': ['serverchan'],
        'useOwnCredential': True,
        'credIds': {'serverchan': cid, 'pushplus': None, 'email': None},
        'cred': {},
        'notify': {'success': False, 'skip': True, 'fail': False},
    }}
    sch.dispatch_push(resolved, _FakeSchedule(uid), _FakeAcc(), 'skip', reason='平台返回跳过')

    assert len(calls) == 1
    assert '跳过' in calls[0][1]['data']['title']


def _resolved_for(channels, cred_ids=None, cred=None, uid=None):
    return {'push': {
        'channels': channels,
        'useOwnCredential': cred_ids is not None,
        'credIds': cred_ids or {'serverchan': None, 'pushplus': None, 'email': None},
        'cred': cred or {},
        'notify': {'success': True, 'skip': False, 'fail': False},
    }}


def test_send_channel_serverchan_rejected_on_business_code(monkeypatch):
    """ServerChan HTTP 200 但 code!=0（如 key 无效）必须判失败并带回平台原因"""
    from app.services.push_render import send_channel, build_ctx
    monkeypatch.setattr(
        sch.requests, 'post',
        lambda url, **kw: type('R', (), {'status_code': 200,
                                         'json': lambda self: {'code': 400, 'message': '无效的key'}})())
    ctx = build_ctx(_FakeAcc(), _FakeSchedule(1), {}, 'success')
    ok, err = send_channel('serverchan', 'SCTbad', ctx)
    assert ok is False
    assert 'code=400' in err and '无效的key' in err


def test_send_channel_pushplus_rejected_on_business_code(monkeypatch):
    """PushPlus HTTP 200 但 code!=200（如 token 失效）必须判失败并带回平台原因"""
    from app.services.push_render import send_channel, build_ctx
    monkeypatch.setattr(
        sch.requests, 'post',
        lambda url, **kw: type('R', (), {'status_code': 200,
                                         'json': lambda self: {'code': 903, 'msg': 'token验证失败'}})())
    ctx = build_ctx(_FakeAcc(), _FakeSchedule(1), {}, 'success')
    ok, err = send_channel('pushplus', 'PPTbad', ctx)
    assert ok is False
    assert 'code=903' in err and 'token验证失败' in err


def test_send_channel_non_json_response_is_failure(monkeypatch):
    """响应体非 JSON（网关错误页等）不得假报成功"""
    from app.services.push_render import send_channel, build_ctx
    monkeypatch.setattr(
        sch.requests, 'post',
        lambda url, **kw: type('R', (), {'status_code': 502,
                                         'json': lambda self: (_ for _ in ()).throw(ValueError())})())
    ctx = build_ctx(_FakeAcc(), _FakeSchedule(1), {}, 'success')
    ok, err = send_channel('serverchan', 'SCTx', ctx)
    assert ok is False
    assert '502' in err
