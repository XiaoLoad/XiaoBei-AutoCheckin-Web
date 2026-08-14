# 配置层：集中管理应用配置
# 通过环境变量 ENV 切换不同配置（development / production）
import os


class Config:
    """基础配置"""

    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = False
    # 允许跨域的来源（生产环境按需收紧）
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')


class DevelopmentConfig(Config):
    """开发环境配置"""

    DEBUG = True
    ENV = 'development'


class ProductionConfig(Config):
    """生产环境配置"""

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
