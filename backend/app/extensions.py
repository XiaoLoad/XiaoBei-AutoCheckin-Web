# 扩展层：集中初始化第三方扩展
from flask_sqlalchemy import SQLAlchemy

# 全局数据库实例（在应用工厂中通过 db.init_app(app) 绑定）
db = SQLAlchemy()
