# 配置层：集中管理应用配置
# 通过环境变量 ENV 切换不同配置（development / production）
import os


def _str_list(value, default):
    """把逗号分隔的字符串还原为去空白列表，过滤空串"""
    raw = (value or '').split(',')
    items = [v.strip() for v in raw if v.strip()]
    return items or default


class Config:
    """基础配置"""

    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = False
    # 允许跨域的来源（生产环境按需收紧，禁止 '*' 与 credentials 同用）
    CORS_ORIGINS = _str_list(os.getenv('CORS_ORIGINS'), ['http://localhost:5173'])

    # 数据库：MySQL（连接串从 .env 读取）
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'SQLALCHEMY_DATABASE_URI',
        'mysql+pymysql://root:123456@localhost:3306/xiaobei_auto?charset=utf8mb4'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT 凭证
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret-change-me')
    JWT_EXPIRES_HOURS = int(os.getenv('JWT_EXPIRES_HOURS', '12'))


class DevelopmentConfig(Config):
    """开发环境配置"""

    DEBUG = True
    ENV = 'development'


class ProductionConfig(Config):
    """生产环境配置（上线时务必替换密钥与数据库口令）"""

    DEBUG = False
    ENV = 'production'


# 配置映射表
CONFIG_MAP = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}


def get_config(env_name=None):
    """根据环境名返回对应配置类"""
    env_name = env_name or os.getenv('FLASK_ENV', 'default')
    return CONFIG_MAP.get(env_name, CONFIG_MAP['default'])
