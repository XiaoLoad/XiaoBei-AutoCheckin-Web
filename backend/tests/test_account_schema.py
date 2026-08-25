from app.schemas.account_schema import load_create, load_preflight


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
