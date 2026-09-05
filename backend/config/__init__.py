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
    # 连接池：归还连接时回滚 + 取出前探活，避免事务泄漏导致 MySQL 可重复读快照串味
    # （直接表现：跨请求复用的连接读不到刚提交的数据）
    # 容量必须 ≥ 调度器并发（SCHEDULER_MAX_WORKERS，默认 30）：每个签到 job 在
    # 「登录→定位→提交」的整段网络 I/O 期间都持有连接、直到落库才释放，池容量小于
    # 并发 job 数时，高峰期排队的 job 会等满 pool_timeout 整批超时失败（连失败记录都写不进）。
    _sched_workers = int(os.getenv('SCHEDULER_MAX_WORKERS', '30') or 30)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_reset_on_return': 'rollback',
        'pool_pre_ping': True,
        'pool_size': max(10, _sched_workers),
        'max_overflow': 10,
        'pool_timeout': 60,
    }

    # JWT 凭证
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret-change-me')
    JWT_EXPIRES_HOURS = int(os.getenv('JWT_EXPIRES_HOURS', '12'))

    # 图库上传根目录（env 可覆盖；默认仓库内 backend/uploads，已被 gitignore 排除）
    UPLOAD_DIR = os.getenv('UPLOAD_DIR') or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')

    # 请求体上限（超出返回 413）：图库原图上限 5MB，加 multipart 编码开销留余量。
    # 没有该上限时，超大 body 会被先整读进内存才撞上业务层 5MB 校验，存在资源耗尽风险
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024


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
