from app.schemas.account_schema import load_create, load_preflight

# 账号级推送绑定：email 可带收件人覆盖，其余通道只认凭证 id
_BASE = {'account': '18290449672', 'password': 'x1'}


def test_create_ok():
    ok, data, msg, code = load_create({'account': '18290449672', 'password': 'x1', 'type': 'dorm'})
    assert ok and data['account'] == '18290449672' and data['type'] == 'dorm'


def test_create_rejects_empty_account():
    ok, _, msg, _ = load_create({'account': '  ', 'password': 'x'})
    assert not ok


def test_create_rejects_bad_type():
    ok, _, msg, _ = load_create({'account': 'a', 'password': 'x', 'type': 'course'})
    assert not ok


def test_preflight_requires_both():
    ok, _, msg, _ = load_preflight({'account': '18290449672'})
    assert not ok


def test_push_creds_plain_id_and_clearing():
    ok, data, _, _ = load_create({**_BASE, 'pushCreds': {'serverchan': 3, 'pushplus': ''}})
    assert ok and data['pushCreds'] == {'serverchan': 3}

    ok, data, _, _ = load_create({**_BASE, 'pushCreds': {}})
    assert ok and data['pushCreds'] == {}

    ok, data, _, _ = load_create({**_BASE})
    assert ok and 'pushCreds' not in data  # 缺省=不改动


def test_push_creds_email_recipient_forms():
    ok, data, _, _ = load_create({**_BASE, 'pushCreds': {'email': {'credId': 5, 'to': 'b@y.com; a@x.com'}}})
    assert ok and data['pushCreds']['email'] == {'credId': 5, 'to': 'b@y.com, a@x.com'}

    # 只覆盖收件人（凭证沿用配置套）
    ok, data, _, _ = load_create({**_BASE, 'pushCreds': {'email': {'to': 'a@x.com'}}})
    assert ok and data['pushCreds']['email'] == {'to': 'a@x.com'}

    # 只绑凭证，收件人留空即不落 to
    ok, data, _, _ = load_create({**_BASE, 'pushCreds': {'email': {'credId': 5, 'to': ''}}})
    assert ok and data['pushCreds']['email'] == 5


def test_push_creds_rejects_bad_forms():
    # 收件人只对邮件通道有意义
    ok, _, _, code = load_create({**_BASE, 'pushCreds': {'serverchan': {'credId': 1, 'to': 'a@x.com'}}})
    assert not ok and code == 4105

    for bad in ({'email': {'to': '不是邮箱'}},
                {'email': {'credId': 0}},
                {'email': {'credId': True}},
                {'email': {'unknown': 1}},
                {'email': 'abc'}):
        ok, _, _, code = load_create({**_BASE, 'pushCreds': bad})
        assert not ok and code == 4105, bad
