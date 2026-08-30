# 用户管理 API 回归：
# - GET /api/users 仅管理员（列表含全员用户名/角色/额度，普通用户必须 403）
# - 管理员编辑用户改密必须真实生效（历史缺陷：setattr(user, 'password', 明文)
#   挂成瞬时属性被 commit 丢弃，密码看似保存实则未变）
from app.extensions import db
from app.models.user import User


def _ensure_user(username, password):
    """幂等创建目标用户（对齐 conftest 的懒创建口径，密码仅测试环境使用）"""
    u = User.query.filter_by(username=username).first()
    if not u:
        u = User(username=username, role='user', enabled=True, quota=10, used_quota=0)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
    return u


def test_user_list_requires_admin(app_ctx, user_headers, admin_headers):
    client = app_ctx.test_client()

    res = client.get('/api/users', headers=user_headers)
    assert res.status_code == 403

    res = client.get('/api/users', headers=admin_headers)
    assert res.status_code == 200
    assert res.get_json()['code'] == 0
    assert isinstance(res.get_json()['data']['items'], list)


def test_admin_update_user_password_applied(app_ctx, admin_headers):
    u = _ensure_user('tc_pwd_reset', 'old-password-1')
    client = app_ctx.test_client()

    res = client.put(f'/api/users/{u.id}', headers=admin_headers,
                     json={'password': 'new-password-2'})
    assert res.status_code == 200

    # 新密码可登录，旧密码失效（若改密未落库，此断言会反向失败）
    res = client.post('/api/auth/login',
                      json={'account': 'tc_pwd_reset', 'password': 'new-password-2'})
    assert res.get_json()['code'] == 0
    res = client.post('/api/auth/login',
                      json={'account': 'tc_pwd_reset', 'password': 'old-password-1'})
    assert res.get_json()['code'] == 1002


def test_admin_update_user_other_fields_still_work(app_ctx, admin_headers):
    """password 改为 set_password 处理后，其余字段的 setattr 更新不受影响"""
    u = _ensure_user('tc_pwd_reset', 'placeholder-1')
    client = app_ctx.test_client()

    res = client.put(f'/api/users/{u.id}', headers=admin_headers, json={'quota': 55})
    assert res.status_code == 200
    assert res.get_json()['data']['quota'] == 55
