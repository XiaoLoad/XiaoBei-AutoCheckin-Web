# 应用工厂：创建并配置 Flask 应用实例
from flask import Flask
from flask_cors import CORS

from config import get_config
from app.utils.response import api_bp  # 健康检查蓝图（统一返回格式演示）
from app.routes.example import bp as example_bp


def create_app(env_name=None):
    app = Flask(__name__)
    app.config.from_object(get_config(env_name))

    # 跨域：开发环境允许前端 5173 端口访问
    CORS(
        app,
        origins=app.config['CORS_ORIGINS'],
        supports_credentials=True,
    )

    # 注册蓝图（按模块划分）
    app.register_blueprint(api_bp)          # /api/health
    app.register_blueprint(example_bp)       # /api/example

    return app
