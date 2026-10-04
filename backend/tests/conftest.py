# pytest 公共夹具：应用上下文（config 无 testing 类，用 development；
# 工厂内 db.create_all 有兜底 try/except，MySQL 未启动时测试仍可跑 crypto 纯逻辑）
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 测试环境关闭调度器自动接管（SCHEDULER_ENABLED=0），避免后台线程干扰用例；
# 调度主链路由 test_scheduler_chain.py 显式驱动验证。须在 create_app 前设置。
os.environ.setdefault('SCHEDULER_ENABLED', '0')

import pytest

from app import create_app


@pytest.fixture(scope='session', autouse=True)
def _purge_test_users_after_session():
    """测试会话结束自动清理全部 tc_* 测试用户（级联清掉名下账号/任务/记录等）。

    测试会在库里创建批量 tc_ 前缀用户并留下启用任务——不清理的话，这些任务
    会在每次平台启动对账时被反复扫到，日志刷「缺少有效执行时刻」噪音、
    执行链还会以解密失败等方式产生无意义的 fail 记录。
    固定用户名（tc_user/tc_admin/tc_push_user 等）由各 fixture 懒创建，
    下次会话自动重建，删除无副作用。MySQL 不可用时静默跳过（纯逻辑用例照常）。"""
    yield
    try:
        app = create_app('development')
        with app.app_context():
            from app.extensions import db
            from app.models.user import User
            from app.services.user_service import purge_user

            victims = User.query.filter(User.username.like('tc\\_%')).all()
            for u in victims:
                try:
                    purge_user(u)
                except Exception:
                    db.session.rollback()
    except Exception:
        # MySQL 未启动等环境缺失场景：让位给用例自身的跳过逻辑
        pass


@pytest.fixture()
def app():
    return create_app('development')


@pytest.fixture()
def app_ctx(app):
    with app.app_context():
        yield app


def _ensure_user(username, role):
    """测试用户懒创建：幂等，密码仅测试环境使用"""
    from app.extensions import db
    from app.models.user import User

    u = User.query.filter_by(username=username).first()
    if not u:
        u = User(username=username, role=role, enabled=True, quota=100, used_quota=0)
        u.set_password('pw-' + username)
        db.session.add(u)
        db.session.commit()
    return u


@pytest.fixture()
def user_headers(app_ctx):
    from app.utils.auth import generate_token
    return {'Authorization': f'Bearer {generate_token(_ensure_user("tc_user", "user"))}'}


@pytest.fixture()
def admin_headers(app_ctx):
    from app.utils.auth import generate_token
    return {'Authorization': f'Bearer {generate_token(_ensure_user("tc_admin", "admin"))}'}
