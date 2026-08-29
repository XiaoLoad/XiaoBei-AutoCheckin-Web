# 应用工厂：创建并配置 Flask 应用实例
import os

from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate

from config import get_config
from app.extensions import db
from app.models import User, SystemConfig, BAccount, ConfigSet  # noqa: F401  确保模型被加载
from app.utils.response import success, error
from app.routes.example import bp as example_bp
from app.routes.health import bp as health_bp
from app.routes.auth import bp as auth_bp
from app.routes.users import bp as users_bp
from app.routes.settings import bp as settings_bp
from app.routes.system import bp as system_bp
from app.routes.accounts import bp as accounts_bp
from app.routes.config_sets import bp as config_sets_bp
from app.routes.schedules import bp as schedules_bp
from app.routes.pools import bp as pools_bp
from app.routes.pool_images import bp as pool_images_bp
from app.routes.tasks import bp as tasks_bp
from app.services.scheduler import init_scheduler


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

    # 数据库结构以迁移链为唯一事实源（Flask-Migrate/Alembic）。
    # directory 用绝对路径：CLI（flask db ...）与工厂启动的工作目录可能不同，
    # 相对路径会有一边找不到迁移脚本。
    migrations_dir = _migrations_dir(app)
    Migrate(app, db, directory=migrations_dir)

    # 注册蓝图（按模块划分）
    app.register_blueprint(health_bp)        # /api/health
    app.register_blueprint(example_bp)       # /api/example
    app.register_blueprint(auth_bp)          # /api/auth
    app.register_blueprint(users_bp)         # /api/users
    app.register_blueprint(settings_bp)      # /api/settings
    app.register_blueprint(system_bp)        # /api/system
    app.register_blueprint(accounts_bp)      # /api/accounts
    app.register_blueprint(config_sets_bp)   # /api/config-sets
    app.register_blueprint(schedules_bp)     # /api/schedules
    app.register_blueprint(pools_bp)         # /api/pools
    app.register_blueprint(pool_images_bp)   # /api/pools/images（图库上传/回收站/文件流）
    app.register_blueprint(tasks_bp)          # /api/tasks（任务日志：跨账号执行日志 + 追踪签到任务）

    # 启动时对齐数据库结构与种子数据；失败不阻断应用启动，
    # 但必须记日志——否则数据库不可用时应用照常起来，排障无从下手。
    try:
        with app.app_context():
            _init_database(app)
            _seed_default_config_sets(app)
            _purge_trash_safely(app)
    except Exception:
        app.logger.exception('启动初始化失败：数据库结构/种子数据未就绪（应用继续启动，相关接口将在调用时报错）')

    # 启动调度器主链路（事件钩子 + 对账兜底）；失败不阻断应用启动。
    try:
        init_scheduler(app)
    except Exception:
        app.logger.exception('调度器启动失败（Web 服务不受影响，定时任务不会执行）')

    return app


def _migrations_dir(app):
    """迁移脚本目录：backend/migrations（app 包的上一级）"""
    return os.path.join(os.path.dirname(app.root_path), 'migrations')


def _init_database(app):
    """启动时把数据库结构对齐到迁移链。按库的形态分三条路径：
    - 空库（无业务表）：upgrade 从 baseline 全量建表；
    - 历史 create_all 建的既有库（无 alembic_version）：stamp head 收编纳管、不做 DDL——
      这些库的增量列此前由启动期补列兜底，结构已与当前 models 一致；
    - 已纳管库：upgrade 应用尚未执行的迁移。
    失败由调用方记日志，不阻断启动。"""
    from sqlalchemy import inspect as sa_inspect
    from flask_migrate import stamp, upgrade

    migrations_dir = _migrations_dir(app)
    if not os.path.isdir(migrations_dir):
        app.logger.warning('迁移目录不存在（%s），跳过数据库结构初始化', migrations_dir)
        return

    insp = sa_inspect(db.engine)
    try:
        if not insp.has_table('users'):
            upgrade(directory=migrations_dir)
        elif not insp.has_table('alembic_version'):
            stamp(directory=migrations_dir, revision='head')
        else:
            upgrade(directory=migrations_dir)
    except SystemExit:
        # flask_migrate 把 alembic 的 CommandError 打印后转成 sys.exit(1)；
        # SystemExit 不走 except Exception，这里转回普通异常交给调用方记日志
        raise RuntimeError('数据库迁移执行失败（ alembic 错误已打印在上方）')


def _seed_default_config_sets(app):
    """为每个用户保证至少一条 is_default 配置套：无套则建空默认套，有套无默认则提升第一条。"""
    try:
        with app.app_context():
            users = User.query.all()
            for u in users:
                default = ConfigSet.query.filter_by(user_id=u.id, is_default=True).first()
                if default:
                    continue
                first = ConfigSet.query.filter_by(user_id=u.id).order_by(ConfigSet.id.asc()).first()
                if first:
                    first.is_default = True
                else:
                    s = ConfigSet(user_id=u.id, name='默认配置套', is_default=True)
                    s.set_config({})
                    db.session.add(s)
            db.session.commit()
    except Exception:
        app.logger.exception('播种用户默认配置套失败')
        try:
            db.session.rollback()
        except Exception:
            pass


def _purge_trash_safely(app):
    """启动时物理清除超期回收站图片；失败记日志不阻断启动"""
    try:
        from app.services.image_store import purge_expired_trash
        purge_expired_trash()
    except Exception:
        app.logger.exception('启动清理超期回收站图片失败')
