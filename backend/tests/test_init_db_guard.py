# S8 回归：init_db 种子脚本守卫——弱口令种子永远进不了真实库
#
# 守卫两条（脚本 _guard，在触碰任何数据库之前执行）：
#   ① FLASK_ENV=production 拒绝；② 连接串不是开发默认值拒绝（改写即疑似真实库）。
# 用例只测守卫本身（SystemExit + 未建表未写用户），不需要 MySQL 可用。
import importlib
import sys
from unittest.mock import patch

import pytest

from app import _DEV_DEFAULT_DB_URI

_SCRIPTS_DIR = None  # 由 _load_script 填充


def _load_script():
    """以模块方式加载 scripts/init_db.py（不在包路径内，手动插 sys.path）。"""
    import os

    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    return importlib.import_module('init_db')


@pytest.fixture()
def init_db_script():
    return _load_script()


def test_refuses_production_env(init_db_script, monkeypatch):
    """A 守卫：FLASK_ENV=production 一律拒绝，即使连接串仍是开发默认值。"""
    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.setenv('SQLALCHEMY_DATABASE_URI', _DEV_DEFAULT_DB_URI)
    with pytest.raises(SystemExit) as exc:
        init_db_script._guard()
    assert 'FLASK_ENV=production' in str(exc.value)


def test_refuses_non_default_db_uri(init_db_script, monkeypatch):
    """A 守卫：连接串被改写即疑似真实库，development 模式同样拒绝。"""
    monkeypatch.setenv('FLASK_ENV', 'development')
    monkeypatch.setenv('SQLALCHEMY_DATABASE_URI',
                       'mysql+pymysql://root:strong-pwd@10.0.0.8:3306/xiaobei_auto?charset=utf8mb4')
    with pytest.raises(SystemExit) as exc:
        init_db_script._guard()
    assert '连接串不是开发默认值' in str(exc.value)


def test_allows_default_dev_setup(init_db_script, monkeypatch):
    """放行路径：development + 开发默认连接串（本地联调的标准形态）不拦截。"""
    monkeypatch.setenv('FLASK_ENV', 'development')
    monkeypatch.setenv('SQLALCHEMY_DATABASE_URI', _DEV_DEFAULT_DB_URI)
    init_db_script._guard()  # 不抛即通过


def test_seed_specs_carry_no_password(init_db_script):
    """B 守卫的数据面：SEED_USERS 不再含 password 字段——弱口令从仓库消失，
    密码只在创建时随机生成并终端显示一次。"""
    assert all('password' not in spec for spec in init_db_script.SEED_USERS)


def test_main_guard_short_circuits_before_db(init_db_script, monkeypatch):
    """守卫必须发生在 create_app 之前：生产环境下 main() 在建应用前就退出。"""
    monkeypatch.setenv('FLASK_ENV', 'production')
    with patch.object(init_db_script, 'create_app') as mock_create:
        with pytest.raises(SystemExit):
            init_db_script.main()
    mock_create.assert_not_called()
