# 账号级推送凭证绑定（pushCreds）回归：
# 覆盖 schema 清洗、PUT/GET 往返、清空语义、非法入参，以及绑定对凭证删除的拦截。
# 账号用 ORM 直建，避免走 B 平台校验；只改 pushCreds 时 update 不触发重校验。
import json

import pytest

from app.extensions import db
from app.models import BAccount, ConfigSet, PoolCredential
from app.models.user import User
from app.services.crypto import encrypt

ACC_NAME = 'tc_pc_acc'


@pytest.fixture()
def seeded(app_ctx, user_headers):
    """建一个账号 + 两个凭证（serverchan / email），退出时按 user_id 清理"""
    u = User.query.filter_by(username='tc_user').first()

    def _cred(channel):
        c = PoolCredential(user_id=u.id, channel=channel, name=f'tc_pc_{channel}',
                           secret_enc=encrypt(json.dumps({'k': 'v'})), enabled=True)
        db.session.add(c)
        db.session.commit()
        return c.id

    acc = BAccount(user_id=u.id, account=ACC_NAME)
    acc.set_password('pw')
    db.session.add(acc)
    db.session.commit()
    sc_id, mail_id = _cred('serverchan'), _cred('email')
    try:
        yield acc.id, sc_id, mail_id
    finally:
        BAccount.query.filter_by(account=ACC_NAME).delete()
        PoolCredential.query.filter_by(name='tc_pc_serverchan').delete()
        PoolCredential.query.filter_by(name='tc_pc_email').delete()
        db.session.commit()


def test_bind_then_list_roundtrip(app, user_headers, seeded):
    acc_id, sc_id, mail_id = seeded
    c = app.test_client()

    r = c.put(f'/api/accounts/{acc_id}', headers=user_headers,
              json={'pushCreds': {'serverchan': sc_id, 'email': mail_id}})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['data']['pushCreds'] == {'serverchan': sc_id, 'email': mail_id}

    items = c.get('/api/accounts', headers=user_headers).get_json()['data']['items']
    row = next(i for i in items if i['id'] == acc_id)
    assert row['pushCreds'] == {'serverchan': sc_id, 'email': mail_id}


def test_blank_values_dropped_and_empty_object_clears(app, user_headers, seeded):
    acc_id, sc_id, _ = seeded
    c = app.test_client()

    r = c.put(f'/api/accounts/{acc_id}', headers=user_headers,
              json={'pushCreds': {'serverchan': sc_id, 'pushplus': ''}})
    assert r.get_json()['data']['pushCreds'] == {'serverchan': sc_id}

    r = c.put(f'/api/accounts/{acc_id}', headers=user_headers, json={'pushCreds': {}})
    assert r.status_code == 200
    assert r.get_json()['data']['pushCreds'] == {}
    # 全空不应留下空对象字符串
    assert db.session.get(BAccount, acc_id).push_cred_json is None


def test_rejects_unknown_channel_and_bad_value(app, user_headers, seeded):
    acc_id, sc_id, _ = seeded
    c = app.test_client()

    r = c.put(f'/api/accounts/{acc_id}', headers=user_headers,
              json={'pushCreds': {'wechat': sc_id}})
    assert r.status_code == 400
    assert r.get_json()['code'] == 4105

    r = c.put(f'/api/accounts/{acc_id}', headers=user_headers,
              json={'pushCreds': {'serverchan': True}})
    assert r.status_code == 400

    r = c.put(f'/api/accounts/{acc_id}', headers=user_headers,
              json={'pushCreds': {'serverchan': -1}})
    assert r.status_code == 400


def test_missing_push_creds_leaves_binding_untouched(app, user_headers, seeded):
    """不带 pushCreds 的更新（如仅切启用状态）不得清掉已有绑定"""
    acc_id, sc_id, _ = seeded
    c = app.test_client()

    c.put(f'/api/accounts/{acc_id}', headers=user_headers,
          json={'pushCreds': {'serverchan': sc_id}})
    r = c.put(f'/api/accounts/{acc_id}', headers=user_headers, json={'enabled': False})
    assert r.get_json()['data']['pushCreds'] == {'serverchan': sc_id}


# ---------- 凭证删除保护：账号绑定是配置套之外的第二处引用来源 ----------

def test_bound_credential_blocked_from_deletion(app, user_headers, seeded):
    """被账号绑定的凭证不得删除；email 走 {credId, to} 形态同样要算进引用"""
    acc_id, sc_id, mail_id = seeded
    c = app.test_client()
    c.put(f'/api/accounts/{acc_id}', headers=user_headers,
          json={'pushCreds': {'serverchan': sc_id,
                              'email': {'credId': mail_id, 'to': 'a@x.com'}}})

    r = c.delete(f'/api/pools/credentials/{sc_id}', headers=user_headers)
    assert r.status_code == 409
    body = r.get_json()
    assert body['code'] == 4323
    # 只有账号引用：配置套计数必须是 0，否则无从判断该找哪儿解绑
    assert body['data'] == {'refs': 0, 'accountRefs': 1}
    assert '1 个账号' in body['message']

    r = c.delete(f'/api/pools/credentials/{mail_id}', headers=user_headers)
    assert r.status_code == 409 and r.get_json()['data']['accountRefs'] == 1

    # 解绑后即可删除
    c.put(f'/api/accounts/{acc_id}', headers=user_headers, json={'pushCreds': {}})
    assert c.delete(f'/api/pools/credentials/{sc_id}', headers=user_headers).status_code == 200
    assert c.delete(f'/api/pools/credentials/{mail_id}', headers=user_headers).status_code == 200


def test_credential_refs_report_config_set_and_account(app, user_headers, seeded):
    """配置套与账号同时引用时两处计数都要上报（只报一处会让用户找不到解绑入口）"""
    acc_id, sc_id, _ = seeded
    cs = ConfigSet(user_id=User.query.filter_by(username='tc_user').first().id,
                   name='tc_pc_引用套', is_default=False)
    cs.set_config({'push': {'channels': ['serverchan'], 'credIds': {'serverchan': sc_id}}})
    db.session.add(cs)
    db.session.commit()
    try:
        c = app.test_client()
        c.put(f'/api/accounts/{acc_id}', headers=user_headers,
              json={'pushCreds': {'serverchan': sc_id}})
        body = c.delete(f'/api/pools/credentials/{sc_id}', headers=user_headers).get_json()
        assert body['code'] == 4323
        assert body['data'] == {'refs': 1, 'accountRefs': 1}
        assert '1 个配置套' in body['message'] and '1 个账号' in body['message']
    finally:
        ConfigSet.query.filter_by(name='tc_pc_引用套').delete()
        db.session.commit()
