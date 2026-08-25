# 应用工厂：创建并配置 Flask 应用实例
from flask import Flask
from flask_cors import CORS

from config import get_config
from app.extensions import db
from app.models import User, SystemConfig, BAccount  # noqa: F401  确保模型被加载
from app.utils.response import success, error
from app.routes.example import bp as example_bp
from app.routes.health import bp as health_bp
from app.routes.auth import bp as auth_bp
from app.routes.users import bp as users_bp
from app.routes.settings import bp as settings_bp
from app.routes.system import bp as system_bp
from app.routes.accounts import bp as accounts_bp


def create_app(env_name=None):
    app = Flask(__name__)
    app.config.from_object(get_config(env_name))

    # 跨域：开发环境允许前端 5173 端口访问，并放行 Authorization 头
    CORS(
        app,
        origins=app.config['CORS_ORIGINS'],
        supports_credentials=True,
        allow_headers=['Content-Type', 'Authorization'],
    )

    # 绑定数据库扩展
    db.init_app(app)

    # 注册蓝图（按模块划分）
    app.register_blueprint(health_bp)        # /api/health
    app.register_blueprint(example_bp)       # /api/example
    app.register_blueprint(auth_bp)          # /api/auth
    app.register_blueprint(users_bp)         # /api/users
    app.register_blueprint(settings_bp)      # /api/settings
    app.register_blueprint(system_bp)        # /api/system
    app.register_blueprint(accounts_bp)      # /api/accounts

    # 启动时自动建表（开发/联调便捷；生产环境建议改用迁移工具）。
    # 兜底捕获：数据库不可用时不影响应用启动，相关接口会在被调用时返回错误。
    try:
        with app.app_context():
            db.create_all()
            _ensure_user_columns(app)
    except Exception:
        pass

    return app


def _ensure_user_columns(app):
    """
    幂等补齐 users 表新增列（quota / used_quota）。
    项目以 db.create_all() 初始化、未引入迁移工具，已存在的表不会被自动 ALTER，
    故在启动时对缺失列做一次补齐；数据库不可用时静默跳过，不阻断启动。
    """
    needed = {
        'quota': 'INT NOT NULL DEFAULT 100',
        'used_quota': 'INT NOT NULL DEFAULT 0',
    }
    try:
        from sqlalchemy import inspect as sa_inspect, text

        with app.app_context():
            insp = sa_inspect(db.engine)
            if not insp.has_table('users'):
                return
            existing = {c['name'] for c in insp.get_columns('users')}
            for col, ddl in needed.items():
                if col not in existing:
                    db.session.execute(text(f'ALTER TABLE users ADD COLUMN {col} {ddl}'))
            db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
