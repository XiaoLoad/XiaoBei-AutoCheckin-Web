# 「账户信息」只读端点测试：鉴权、身份字段、额度口径（上限取 quota、已用恒等于账号数现算）
from app.extensions import db
from app.models import BAccount, User
from app.models.user import now_cst
from app.utils.auth import generate_token


def _seed_user(accounts=0, quota=100):
    """独立测试用户：按需挂 N 个平台账号，返回 (user, headers)。"""
    uname = f'tc_ai_{now_cst().strftime("%H%M%S%f")}'
    u = User(username=uname, role='user', enabled=True, quota=quota)
    u.set_password('pw')
    u.last_login = now_cst()
    db.session.add(u)
    db.session.flush()
    for i in range(accounts):
        db.session.add(BAccount(user_id=u.id, account=f'ai_acc_{i}', password_enc='x'))
    db.session.commit()
    headers = {'Authorization': f'Bearer {generate_token(u)}'}
    return u, headers


def _cleanup(u):
    BAccount.query.filter_by(user_id=u.id).delete()
    db.session.delete(u)
    db.session.commit()


def test_account_info_requires_auth(app):
    c = app.test_client()
    assert c.get('/api/me/account-info').status_code in (401, 403)


def test_account_info_identity_and_quota(app, app_ctx):
    c = app.test_client()
    u, headers = _seed_user(accounts=2, quota=100)
    try:
        res = c.get('/api/me/account-info', headers=headers)
        assert res.status_code == 200
        data = res.get_json()['data']
        assert data['username'] == u.username
        assert data['role'] == 'user'
        # 身份体征：注册/最近登录均已落值（种子时显式赋 last_login）
        assert data['createdAt']
        assert data['lastLogin']
        # 额度口径：已用 = 账号数现算（不读 used_quota 计数器），2/100 → 2%
        assert data['quota'] == {'used': 2, 'limit': 100, 'pct': 2}
    finally:
        _cleanup(u)


def test_account_info_empty_quota(app, app_ctx):
    c = app.test_client()
    u, headers = _seed_user(accounts=0, quota=100)
    try:
        data = c.get('/api/me/account-info', headers=headers).get_json()['data']
        assert data['quota'] == {'used': 0, 'limit': 100, 'pct': 0}
    finally:
        _cleanup(u)


def test_account_info_zero_limit_no_divide_error(app, app_ctx):
    c = app.test_client()
    u, headers = _seed_user(accounts=0, quota=0)
    try:
        data = c.get('/api/me/account-info', headers=headers).get_json()['data']
        # 上限为 0 时不做除法，使用率稳定为 0
        assert data['quota'] == {'used': 0, 'limit': 0, 'pct': 0}
    finally:
        _cleanup(u)
