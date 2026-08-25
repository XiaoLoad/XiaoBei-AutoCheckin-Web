# pytest 公共夹具：应用上下文（config 无 testing 类，用 development；
# 工厂内 db.create_all 有兜底 try/except，MySQL 未启动时测试仍可跑 crypto 纯逻辑）
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app import create_app


@pytest.fixture()
def app():
    return create_app('development')


@pytest.fixture()
def app_ctx(app):
    with app.app_context():
        yield app
