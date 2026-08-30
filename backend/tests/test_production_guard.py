# 生产环境密钥守护回归：ENV=production 且密钥仍为仓库可见的开发默认值时，
# create_app 必须拒绝启动（SECRET_KEY 派生凭据加密、JWT 签发会话，默认值等于裸奔）
import pytest

from app import create_app
from config import ProductionConfig


@pytest.fixture()
def _prod_secrets():
    """临时替换 ProductionConfig 密钥为合规值（类属性在 import 时求值，测试内直改并还原）"""
    saved = (ProductionConfig.SECRET_KEY, ProductionConfig.JWT_SECRET_KEY,
             ProductionConfig.SQLALCHEMY_DATABASE_URI)
    ProductionConfig.SECRET_KEY = 'prod-secret-not-default-0123456789'
    ProductionConfig.JWT_SECRET_KEY = 'prod-jwt-secret-not-default-0123456789'
    ProductionConfig.SQLALCHEMY_DATABASE_URI = (
        'mysql+pymysql://prod_user:strong-pass@db.host:3306/xiaobei_auto?charset=utf8mb4')
    yield
    (ProductionConfig.SECRET_KEY, ProductionConfig.JWT_SECRET_KEY,
     ProductionConfig.SQLALCHEMY_DATABASE_URI) = saved


def test_production_rejects_dev_default_secrets():
    with pytest.raises(RuntimeError) as ei:
        create_app('production')
    msg = str(ei.value)
    assert 'SECRET_KEY' in msg and 'JWT_SECRET_KEY' in msg and '数据库连接串' in msg


def test_production_accepts_configured_secrets(_prod_secrets):
    app = create_app('production')
    assert app.config['ENV'] == 'production'


def test_development_still_boots_with_defaults():
    # 开发环境不守守护（否则本地起不来）；development + 默认密钥必须照常创建
    app = create_app('development')
    assert app.config['DEBUG'] is True
