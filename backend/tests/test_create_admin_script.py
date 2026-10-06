# create_admin.py 首个管理员创建脚本回归：
# 核心约束——仅当 users 表为空时允许建号（防绕过界面造号）、密码策略与
# API 入口同一套规则（password_min_length 下限 + bcrypt 72 字节上限）、
# 用户名走统一校验器。
# 同时覆盖启动自动引导 _bootstrap_first_admin（默认路径）的幂等与建号行为。
import pytest

from app.extensions import db
from app.models.user import User
from scripts.create_admin import create_first_admin


@pytest.fixture()
def _purge_tc():
    yield
    db.session.query(User).filter(User.username.like('tc_first%')).delete()
    db.session.commit()


def test_refuses_when_any_user_exists(app_ctx):
    """系统已有账号（如开发种子 admin）时必须拒绝，防止绕过界面造号"""
    with pytest.raises(SystemExit) as ei:
        create_first_admin('tc_first_x', 'whatever-password')
    assert '已存在账号' in str(ei.value)


def test_creates_first_admin_when_table_empty(app_ctx, monkeypatch, _purge_tc):
    """users 表为空（全新部署）：建号成功且角色为 admin、密码哈希可校验"""
    from types import SimpleNamespace

    monkeypatch.setattr(User, 'query', SimpleNamespace(count=lambda: 0))
    admin = create_first_admin('tc_first_admin', 'S3cure-Passw0rd!')
    assert admin.role == 'admin'
    assert admin.enabled is True
    row = db.session.query(User).filter_by(username='tc_first_admin').first()
    assert row is not None
    assert row.check_password('S3cure-Passw0rd!')


def test_refuses_short_password(app_ctx, monkeypatch):
    """密码长度走系统设置 password_min_length 下限，与 API 入口一致"""
    from types import SimpleNamespace

    monkeypatch.setattr(User, 'query', SimpleNamespace(count=lambda: 0))
    with pytest.raises(SystemExit) as ei:
        create_first_admin('tc_first_x', '123')
    assert '密码至少' in str(ei.value)


def test_refuses_overlong_password(app_ctx, monkeypatch):
    """超过 bcrypt 72 字节上限的密码拒绝，不静默截断"""
    from types import SimpleNamespace

    monkeypatch.setattr(User, 'query', SimpleNamespace(count=lambda: 0))
    with pytest.raises(SystemExit) as ei:
        create_first_admin('tc_first_x', 'a' * 73)
    assert '72' in str(ei.value)


def test_refuses_invalid_username(app_ctx, monkeypatch):
    """用户名走与接口一致的校验器"""
    from types import SimpleNamespace

    monkeypatch.setattr(User, 'query', SimpleNamespace(count=lambda: 0))
    with pytest.raises(SystemExit) as ei:
        create_first_admin('', 'S3cure-Passw0rd!')
    assert '用户名' in str(ei.value)


# ───────────────────────── 启动自动引导 _bootstrap_first_admin ─────────────────────────

def test_bootstrap_creates_admin_when_table_empty(app_ctx, monkeypatch, _purge_tc):
    """users 表为空（全新部署）：引导建号成功，返回的随机密码可校验通过"""
    from types import SimpleNamespace

    from flask import current_app

    from app import _bootstrap_first_admin

    monkeypatch.setattr(User, 'query', SimpleNamespace(count=lambda: 0))
    password = _bootstrap_first_admin(current_app._get_current_object(),
                                      username='tc_first_boot')
    assert password
    row = db.session.query(User).filter_by(username='tc_first_boot').first()
    assert row is not None
    assert row.role == 'admin'
    assert row.enabled is True
    assert row.check_password(password)


def test_bootstrap_skips_when_users_exist(app_ctx):
    """users 非空（开发种子库/正常运行）：引导跳过，不新建账号、不返回密码"""
    from flask import current_app

    from app import _bootstrap_first_admin

    before = User.query.count()
    assert before > 0
    assert _bootstrap_first_admin(current_app._get_current_object()) is None
    assert User.query.count() == before
