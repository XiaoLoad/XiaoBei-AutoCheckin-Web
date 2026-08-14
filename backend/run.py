# 本地开发启动脚本
# 用法：python run.py  （默认监听 http://127.0.0.1:5000）
import os
import sys

# 确保 backend 目录在 sys.path 中，使 `from config` / `from app` 可解析
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

if __name__ == '__main__':
    env = os.getenv('FLASK_ENV', 'development')
    app = create_app(env)
    app.run(host='0.0.0.0', port=5000, debug=app.config['DEBUG'])
