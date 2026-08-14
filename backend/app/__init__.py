# 应用工厂：创建并配置 Flask 应用实例
from flask import Flask
from flask_cors import CORS

from config import get_config
from app.extensions import db
from app.models import User  # noqa: F401  确保模型被加载
from app.utils.response import api_bp  # 健康检查蓝图（统一返回格式演示）
from app.routes.example import bp as example_bp
from app.routes.auth import bp as auth_bp


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
    app.register_blueprint(api_bp)          # /api/health
    app.register_blueprint(example_bp)       # /api/example
    app.register_blueprint(auth_bp)          # /api/auth

    # 启动时自动建表（开发/联调便捷；生产环境建议改用迁移工具）。
    # 兜底捕获：数据库不可用时不影响应用启动，相关接口会在被调用时返回错误。
    try:
        with app.app_context():
            db.create_all()
    except Exception:
        pass

    return app
