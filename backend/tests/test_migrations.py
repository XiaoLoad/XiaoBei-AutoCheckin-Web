# 迁移链对账：baseline 迁移在空库上建出的结构必须与 models 定义一致。
# 三条启动路径中，「旧库 stamp 收编」由每次测试会话在开发库上自然覆盖
# （conftest 经 create_app 触发 _init_database），这里只校验「全新建库」路径。
import os
import re

import pytest
from flask import Flask
from sqlalchemy import create_engine, inspect, text

from app.extensions import db
from config import get_config

MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'migrations')
SCRATCH_DB = 'xiaobei_auto_migration_test'


def _scratch_uri():
    """把配置里的库名替换为临时库名，连接凭据与开发库保持一致"""
    base = get_config().SQLALCHEMY_DATABASE_URI
    scratch = re.sub(r'/[^/?]+(\?|$)', rf'/{SCRATCH_DB}\1', base)
    if scratch == base:
        pytest.skip('无法从连接串解析库名，跳过迁移对账')
    return base, scratch


def test_baseline_upgrade_matches_models():
    if not os.path.isdir(MIGRATIONS_DIR):
        pytest.skip('migrations 目录不存在，跳过迁移对账')

    base_uri, scratch_uri = _scratch_uri()
    # 无库名的管理连接，用于创建/丢弃临时库；无权限时跳过而非失败
    try:
        admin = create_engine(re.sub(r'/[^/?]*(\?|$)', r'/\1', base_uri))
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS {SCRATCH_DB}'))
            conn.execute(text(f'CREATE DATABASE {SCRATCH_DB} CHARACTER SET utf8mb4'))
        admin.dispose()
    except Exception:
        pytest.skip('无权限创建临时数据库，跳过迁移对账')

    try:
        # 独立最小应用（不走工厂）：工厂会把启动初始化绑到开发库连接上
        app = Flask(__name__)
        app.config.from_object(get_config())
        app.config['SQLALCHEMY_DATABASE_URI'] = scratch_uri
        db.init_app(app)
        from flask_migrate import Migrate, upgrade
        Migrate(app, db, directory=MIGRATIONS_DIR)

        with app.app_context():
            upgrade(directory=MIGRATIONS_DIR)
            insp = inspect(db.engine)
            actual = set(insp.get_table_names())
            for name, table in db.metadata.tables.items():
                assert name in actual, f'迁移缺表：{name}'
                model_cols = {c.name for c in table.columns}
                db_cols = {c['name'] for c in insp.get_columns(name)}
                missing = model_cols - db_cols
                assert not missing, f'表 {name} 迁移缺列：{sorted(missing)}'
            assert 'alembic_version' in actual
    finally:
        try:
            admin = create_engine(re.sub(r'/[^/?]*(\?|$)', r'/\1', scratch_uri))
            with admin.connect() as conn:
                conn.execute(text(f'DROP DATABASE IF EXISTS {SCRATCH_DB}'))
            admin.dispose()
        except Exception:
            pass
