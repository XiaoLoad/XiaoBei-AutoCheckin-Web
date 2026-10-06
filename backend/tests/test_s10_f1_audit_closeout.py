# 审计 S10（安全杂项）与 F1（课表解析）收口回归：
# F1.1——课表表格存在但解析出 0 条课程时静默返回空列表，页面结构变更无痕；
#       现行为：抛 JwxtError('parse')，同步侧 fail_count/needs_attention 可感知。
# F1.2——'1-4' 区间写法与枚举歧义且方向是扩窗；现行为：行为不变（区间展开），
#       但展开时记 WARNING 留痕。
# S10.2——无鉴权演示蓝图 /api/example 注册进生产应用（POST 无上限写内存）；
#       现行为：蓝图删除，路由 404。
# S10.3——JWT 黑名单查询 fail-open 且无日志；现行为：降级放行时记 WARNING。
# S10.4——CORS_ORIGINS 配 '*' 时与 supports_credentials 组合反射任意来源，
#       生产守护未校验；现行为：生产环境命中即拒绝启动。
# S10.5——/api/health 未认证返回 env，泄露部署环境名；现行为：只回固定状态。
# S10.6——client_ip 无条件信任 XFF 首段，审计 IP 可伪造；现行为：仅当直连对端
#       是回环/内网可信代理时才采信转发头，公网直连取 remote_addr。
# S10.8——bcrypt 72 字节静默截断 + 密码下限可配到 4 位；现行为：三个密码入口
#       统一拒绝超 72 字节，password_min_length 下限收紧到 6。
import logging

import pytest

from config import ProductionConfig


# ───────────────────────── F1.1：0 课抛错 ─────────────────────────

def test_parse_timetable_raises_when_no_course_parsed():
    """kbtable 存在但无任何课程内容：必须抛错而不是返回空课表"""
    from app.services.jwxt.base import JwxtError
    from app.services.jwxt.parser import parse_timetable

    html = '<html><body><table id="kbtable"><tr><td>第1节</td></tr></table></body></html>'
    with pytest.raises(JwxtError) as ei:
        parse_timetable(html)
    assert ei.value.kind == 'parse'


def test_parse_timetable_missing_table_still_raises():
    """缺 kbtable 维持既有抛错行为（回归）"""
    from app.services.jwxt.base import JwxtError
    from app.services.jwxt.parser import parse_timetable

    with pytest.raises(JwxtError):
        parse_timetable('<html><body><p>404</p></body></html>')


# ───────────────────────── F1.2：区间歧义告警 ─────────────────────────

def test_parse_sections_range_form_warns(caplog):
    """非零填充两段按区间展开（行为不变），但必须记 WARNING 留痕"""
    from app.services.jwxt.parser import _parse_sections

    with caplog.at_level(logging.WARNING, logger='app.services.jwxt.parser'):
        result = _parse_sections('1-4')
    assert result == [1, 2, 3, 4]
    assert any('歧义' in r.message for r in caplog.records)


def test_parse_sections_zero_padded_enum_no_warning(caplog):
    """零填充枚举是权威语法，展开 8 节也不得告警（回归）"""
    from app.services.jwxt.parser import _parse_sections

    with caplog.at_level(logging.WARNING, logger='app.services.jwxt.parser'):
        assert _parse_sections('01-02-03-04-05-06-07-08') == [1, 2, 3, 4, 5, 6, 7, 8]
        assert _parse_sections('01-02') == [1, 2]
    assert caplog.records == []


# ───────────────────────── S10.2：示例蓝图移除 ─────────────────────────

def test_example_blueprint_removed(app):
    c = app.test_client()
    assert c.get('/api/example').status_code == 404


# ───────────────────────── S10.3：黑名单 fail-open 留痕 ─────────────────────────

def test_is_blacklisted_failopen_logs_warning(app_ctx, caplog, monkeypatch):
    from types import SimpleNamespace

    import app.utils.auth as auth_mod

    def _boom(*_a, **_k):
        raise RuntimeError('db down')

    fake_db = SimpleNamespace(session=SimpleNamespace(get=_boom))
    monkeypatch.setattr(auth_mod, 'db', fake_db)

    with caplog.at_level(logging.WARNING):
        assert auth_mod.is_blacklisted('somejti1234') is False
    assert any('黑名单查询失败' in r.message for r in caplog.records)


# ───────────────────────── S10.4：CORS 通配符生产守护 ─────────────────────────

@pytest.fixture()
def _prod_secrets():
    saved = (ProductionConfig.SECRET_KEY, ProductionConfig.JWT_SECRET_KEY,
             ProductionConfig.SQLALCHEMY_DATABASE_URI)
    ProductionConfig.SECRET_KEY = 'prod-secret-not-default-0123456789'
    ProductionConfig.JWT_SECRET_KEY = 'prod-jwt-secret-not-default-0123456789'
    ProductionConfig.SQLALCHEMY_DATABASE_URI = (
        'mysql+pymysql://prod_user:strong-pass@db.host:3306/xiaobei_auto?charset=utf8mb4')
    yield
    (ProductionConfig.SECRET_KEY, ProductionConfig.JWT_SECRET_KEY,
     ProductionConfig.SQLALCHEMY_DATABASE_URI) = saved


def test_production_rejects_cors_wildcard(_prod_secrets):
    from app import create_app

    saved = ProductionConfig.CORS_ORIGINS
    ProductionConfig.CORS_ORIGINS = ['*']
    try:
        with pytest.raises(RuntimeError) as ei:
            create_app('production')
        assert 'CORS_ORIGINS' in str(ei.value)
    finally:
        ProductionConfig.CORS_ORIGINS = saved


def test_production_accepts_explicit_origins(_prod_secrets):
    from app import create_app

    saved = ProductionConfig.CORS_ORIGINS
    ProductionConfig.CORS_ORIGINS = ['https://checkin.example.com']
    try:
        app = create_app('production')
        assert app.config['ENV'] == 'production'
    finally:
        ProductionConfig.CORS_ORIGINS = saved


# ───────────────────────── S10.5：health 不泄露 env ─────────────────────────

def test_health_returns_no_env(app):
    c = app.test_client()
    r = c.get('/api/health')
    assert r.status_code == 200
    body = r.get_json()
    assert body['data'] == {'status': 'ok'}
    assert 'env' not in body['data']


# ───────────────────────── S10.6：XFF 仅可信代理采信 ─────────────────────────

def test_client_ip_ignores_xff_from_public_peer(app):
    """公网直连：转发头客户端可随意伪造，必须取真实 TCP 对端"""
    from app.services.op_log import client_ip

    with app.test_request_context(
            '/', environ_base={'REMOTE_ADDR': '8.8.8.8'},
            headers={'X-Forwarded-For': '1.2.3.4'}):
        assert client_ip() == '8.8.8.8'


def test_client_ip_trusts_xff_from_loopback_proxy(app):
    """单机 nginx 反代（remote_addr=127.0.0.1）：取 XFF 首段"""
    from app.services.op_log import client_ip

    with app.test_request_context(
            '/', environ_base={'REMOTE_ADDR': '127.0.0.1'},
            headers={'X-Forwarded-For': '198.51.100.9, 10.0.0.1'}):
        assert client_ip() == '198.51.100.9'


def test_client_ip_trusts_x_real_ip_from_private_proxy(app):
    """内网代理无 XFF 时回落 X-Real-IP；公网对端同样拒绝该头"""
    from app.services.op_log import client_ip

    with app.test_request_context(
            '/', environ_base={'REMOTE_ADDR': '192.168.1.2'},
            headers={'X-Real-IP': '198.51.100.9'}):
        assert client_ip() == '198.51.100.9'

    with app.test_request_context(
            '/', environ_base={'REMOTE_ADDR': '8.8.8.8'},
            headers={'X-Real-IP': '198.51.100.9'}):
        assert client_ip() == '8.8.8.8'


# ───────────────────────── S10.8：密码长度边界 ─────────────────────────

def test_password_too_long_boundary():
    """72 字节为 bcrypt 有效上限：按 UTF-8 字节计，中文 3 字节/字"""
    from app.utils.validators import password_too_long

    assert password_too_long('a' * 72) is False
    assert password_too_long('a' * 73) is True
    assert password_too_long('中' * 24) is False    # 72 字节
    assert password_too_long('中' * 25) is True     # 75 字节
    assert password_too_long('') is False


def test_create_user_rejects_overlong_password(app, admin_headers):
    """管理员新建用户：超 72 字节密码明确拒绝，不被 bcrypt 静默截断"""
    c = app.test_client()
    r = c.post('/api/users', json={
        'username': 'tc_pwdlong', 'password': 'a' * 73, 'role': 'user',
    }, headers=admin_headers)
    assert r.status_code == 400
    assert '72' in r.get_json()['message']


def test_change_password_rejects_overlong_password(app, user_headers):
    """本人改密：新密码超 72 字节拒绝（校验先于任何落库，不产生副作用）"""
    c = app.test_client()
    r = c.put('/api/auth/password', json={
        'old_password': 'pw-tc_user', 'new_password': 'b' * 73,
    }, headers=user_headers)
    assert r.status_code == 400
    assert '72' in r.get_json()['message']


def test_password_min_length_floor_is_six():
    """password_min_length 可配置下限收紧到 6（原为 4）"""
    from app.models.system_config import DEFAULTS

    assert DEFAULTS['password_min_length']['min'] == 6
    assert DEFAULTS['password_min_length']['value'] >= 6
