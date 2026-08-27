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


def _capture(monkeypatch):
    calls = []

    def fake_post(url, **kw):
        calls.append((url, kw))
        return type('R', (), {'status_code': 200})()

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
