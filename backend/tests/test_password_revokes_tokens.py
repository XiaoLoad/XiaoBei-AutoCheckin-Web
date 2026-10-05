# S7 回归：修改密码后吊销该用户全部存量 token（pwd_ver 机制）
#
# JWT 无状态、无法枚举某用户的全部 jti，黑名单只适合单 token 吊销（注销场景）；
# 改密吊销走密码版本号：token 携带签发时的 pwd_ver，鉴权时与库值比对，不等即拒。
# 覆盖两条改密入口：本人改密（auth.py /password）与管理员重置（users.py PUT）。
from app.extensions import db
from app.models.user import User
from app.utils.auth import generate_token
from tests.conftest import _ensure_user


def _mk_user(username, role='user'):
    u = _ensure_user(username, role)
    u.pwd_ver = 1
    db.session.commit()
    return u


def test_change_password_revokes_existing_token(app_ctx):
    """本人改密：改密前签发的 token 立即失效（401/1007），用新密码重新登录后恢复。"""
    u = _mk_user('tc_pwdver_self')
    client = app_ctx.test_client()
    old_headers = {'Authorization': f'Bearer {generate_token(u)}'}

    # 改密前 token 可用
    assert client.get('/api/auth/me', headers=old_headers).status_code == 200

    res = client.put('/api/auth/password', headers=old_headers,
                     json={'old_password': 'pw-tc_pwdver_self', 'new_password': 'pw-new-123'})
    assert res.get_json()['code'] == 0

    # 改密后同一 token 立即被吊销（REVOKED），而不是存活到 exp
    me = client.get('/api/auth/me', headers=old_headers)
    assert me.status_code == 401
    assert me.get_json()['code'] == 1007

    # 新密码重新登录 → 新 token 携带新 pwd_ver，恢复正常访问
    login = client.post('/api/auth/login',
                        json={'account': 'tc_pwdver_self', 'password': 'pw-new-123'})
    assert login.get_json()['code'] == 0
    new_headers = {'Authorization': f"Bearer {login.get_json()['data']['token']}"}
    assert client.get('/api/auth/me', headers=new_headers).status_code == 200


def test_admin_reset_revokes_target_tokens(app_ctx, admin_headers):
    """管理员重置密码：目标用户在其它设备持有的 token 同步失效（S7 的核心场景）。"""
    u = _mk_user('tc_pwdver_reset')
    client = app_ctx.test_client()
    victim_headers = {'Authorization': f'Bearer {generate_token(u)}'}
    assert client.get('/api/auth/me', headers=victim_headers).status_code == 200

    res = client.put(f'/api/users/{u.id}', headers=admin_headers,
                     json={'password': 'pw-reset-456'})
    assert res.get_json()['code'] == 0

    me = client.get('/api/auth/me', headers=victim_headers)
    assert me.status_code == 401
    assert me.get_json()['code'] == 1007


def test_other_user_token_unaffected(app_ctx):
    """pwd_ver 按用户隔离：A 改密只吊销 A 的 token，B 的 token 不受牵连。"""
    a = _mk_user('tc_pwdver_a')
    b = _mk_user('tc_pwdver_b')
    client = app_ctx.test_client()
    a_headers = {'Authorization': f'Bearer {generate_token(a)}'}
    b_headers = {'Authorization': f'Bearer {generate_token(b)}'}

    assert client.put('/api/auth/password', headers=a_headers,
                      json={'old_password': 'pw-tc_pwdver_a', 'new_password': 'pw-a-new'}).get_json()['code'] == 0

    assert client.get('/api/auth/me', headers=a_headers).status_code == 401
    assert client.get('/api/auth/me', headers=b_headers).status_code == 200


def test_logout_still_works_after_revoked_token(app_ctx):
    """吊销后的 token 走注销接口同样被拦（黑名单与 pwd_ver 同返回 1007），
    语义一致：都是「登录已失效」。"""
    u = _mk_user('tc_pwdver_logout')
    client = app_ctx.test_client()
    headers = {'Authorization': f'Bearer {generate_token(u)}'}
    assert client.put('/api/auth/password', headers=headers,
                      json={'old_password': 'pw-tc_pwdver_logout', 'new_password': 'pw-lo-new'}).get_json()['code'] == 0

    res = client.post('/api/auth/logout', headers=headers)
    assert res.status_code == 401
    assert res.get_json()['code'] == 1007
