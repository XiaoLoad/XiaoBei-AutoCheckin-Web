# 应用工厂：创建并配置 Flask 应用实例
import logging
import logging.handlers
import os

from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate

from config import get_config
from app.extensions import db
from app.models import User, SystemConfig, BAccount, ConfigSet  # noqa: F401  确保模型被加载
from app.utils.response import success, error
from app.routes.health import bp as health_bp
from app.routes.auth import bp as auth_bp
from app.routes.users import bp as users_bp
from app.routes.settings import bp as settings_bp
from app.routes.system import bp as system_bp
from app.routes.accounts import bp as accounts_bp
from app.routes.jwxt import bp as jwxt_bp
from app.routes.config_sets import bp as config_sets_bp
from app.routes.schedules import bp as schedules_bp
from app.routes.pools import bp as pools_bp
from app.routes.pool_images import bp as pool_images_bp
from app.routes.tasks import bp as tasks_bp
from app.routes.me import bp as me_bp
from app.routes.admin import bp as admin_bp
from app.routes.map import bp as map_bp
from app.routes.op_logs import bp as op_logs_bp
from app.routes.group_push import bp as group_push_bp
from app.services.scheduler import init_scheduler
from app.services.op_log import connect_handlers


def create_app(env_name=None):
    app = Flask(__name__)
    app.config.from_object(get_config(env_name))
    _assert_production_secrets(app)

    # 跨域：开发环境允许前端 5173 端口访问，并放行 Authorization 头
    CORS(
        app,
        origins=app.config['CORS_ORIGINS'],
        supports_credentials=True,
        allow_headers=['Content-Type', 'Authorization'],
    )

    # 绑定数据库扩展
    db.init_app(app)

    # 请求体超限（MAX_CONTENT_LENGTH）统一走 JSON 信封：Flask 默认 413 是 HTML 错误页，
    # 前端 axios 拦截器按 {code, message, data} 解包会拿到 undefined.message
    @app.errorhandler(413)
    def _request_too_large(_e):
        return error(message='上传内容超过大小限制（最大 8MB），请压缩后再试', code=4130, status=413)

    # 数据库结构以迁移链为唯一事实源（Flask-Migrate/Alembic）。
    # directory 用绝对路径：CLI（flask db ...）与工厂启动的工作目录可能不同，
    # 相对路径会有一边找不到迁移脚本。
    migrations_dir = _migrations_dir(app)
    Migrate(app, db, directory=migrations_dir)

    # 注册蓝图（按模块划分）
    app.register_blueprint(health_bp)        # /api/health
    app.register_blueprint(auth_bp)          # /api/auth
    app.register_blueprint(users_bp)         # /api/users
    app.register_blueprint(settings_bp)      # /api/settings
    app.register_blueprint(system_bp)        # /api/system
    app.register_blueprint(accounts_bp)      # /api/accounts
    app.register_blueprint(jwxt_bp)          # /api/b-accounts/:id/jwxt（教务绑定/课表同步/窗口预览）
    app.register_blueprint(config_sets_bp)   # /api/config-sets
    app.register_blueprint(schedules_bp)     # /api/schedules
    app.register_blueprint(pools_bp)         # /api/pools
    app.register_blueprint(pool_images_bp)   # /api/pools/images（图库上传/回收站/文件流）
    app.register_blueprint(tasks_bp)          # /api/tasks（任务日志：跨账号执行日志 + 追踪签到任务）
    app.register_blueprint(me_bp)             # /api/me（个人中心聚合：仪表盘数据源）
    app.register_blueprint(admin_bp)          # /api/admin（管理员仪表盘聚合：全站视角）
    app.register_blueprint(map_bp)            # /api/map（地图服务配置：地图拾取用）
    app.register_blueprint(op_logs_bp)        # /api/op-logs（用户日志：平台操作审计）
    app.register_blueprint(group_push_bp)      # /api/group-push（班级/寝室分组合并推送）

    # 操作审计订阅者：把 app/events.py 发出的用户/认证信号落成 op_logs 流水。
    # 与蓝图注册同批完成，保证任何请求进来之前订阅关系已就绪（进程级幂等）
    connect_handlers()

    # 启动时对齐数据库结构与种子数据；失败不阻断应用启动，
    # 但必须记日志——否则数据库不可用时应用照常起来，排障无从下手。
    try:
        with app.app_context():
            _init_database(app)
            _seed_default_config_sets(app)
            _purge_trash_safely(app)
    except Exception:
        app.logger.exception('启动初始化失败：数据库结构/种子数据未就绪（应用继续启动，相关接口将在调用时报错）')

    # 日志装配必须晚于 _init_database：Alembic 的 migrations/env.py 会 fileConfig(alembic.ini)，
    # 该调用会清掉 root 上已有的处理器并把级别改回 WARNING（[logger_root] level=WARN），
    # 装在前面会被当场销毁，logs/app.log 永远是空文件。
    _setup_logging(app)

    # 启动调度器主链路（事件钩子 + 对账兜底）；失败不阻断应用启动。
    try:
        init_scheduler(app)
    except Exception:
        app.logger.exception('调度器启动失败（Web 服务不受影响，定时任务不会执行）')

    return app


def _migrations_dir(app):
    """迁移脚本目录：backend/migrations（app 包的上一级）"""
    return os.path.join(os.path.dirname(app.root_path), 'migrations')


# 开发默认值（与 config.Config 中的 fallback 保持一致）；生产环境命中即拒绝启动
_DEV_DEFAULT_SECRET_KEY = 'dev-secret-key'
_DEV_DEFAULT_JWT_SECRET = 'dev-jwt-secret-change-me'
_DEV_DEFAULT_DB_URI = 'mysql+pymysql://root:123456@localhost:3306/xiaobei_auto?charset=utf8mb4'


def _assert_production_secrets(app):
    """生产环境密钥守护：SECRET_KEY 派生 Fernet 凭据加密、JWT 签发会话，
    若仍为公开在仓库里的开发默认值，等于凭据与会话对任何拿到代码的人透明。
    命中即拒绝启动（而非降级警告），逼出 .env 配置。"""
    if app.config.get('ENV') != 'production':
        return
    problems = []
    if app.config['SECRET_KEY'] == _DEV_DEFAULT_SECRET_KEY:
        problems.append('SECRET_KEY 仍为开发默认值')
    if app.config['JWT_SECRET_KEY'] == _DEV_DEFAULT_JWT_SECRET:
        problems.append('JWT_SECRET_KEY 仍为开发默认值')
    if app.config['SQLALCHEMY_DATABASE_URI'] == _DEV_DEFAULT_DB_URI:
        problems.append('数据库连接串仍为开发默认（root/123456）')
    if '*' in app.config.get('CORS_ORIGINS', []):
        # supports_credentials 恒开：CORS 配 '*' 等于反射任意来源并携带凭据，
        # 生产环境必须配置明确的来源清单
        problems.append('CORS_ORIGINS 含 "*"（与 credentials 同用会放行任意来源携带凭据）')
    if problems:
        raise RuntimeError(
            '生产环境启动被拒绝：' + '；'.join(problems)
            + '。请在环境变量或 backend/.env 中配置后再以 production 启动'
        )


_logging_configured = False


def _setup_logging(app):
    """全局日志落盘：调度/推送的 INFO 级关键日志（job 注册、执行汇总、推送成败）
    此前不落盘（gunicorn 下仅 WARNING+ 走 stderr），线上排障只剩异常栈。
    - 文件：backend/logs/app.log，5MB × 3 个轮转文件（目录自动创建，*.log 已 gitignore）；
    - 控制台保留 WARNING+（根级别提到 INFO 后需把 werkzeug 压回 WARNING，
      避免每个 HTTP 请求刷屏落盘；开发时请求日志仍由 werkzeug 自己的 stdout 承担）；
    - 进程级幂等：create_app 可能被测试多次调用，模块级标志保证只装配一次。
      调用时机必须在 _init_database 之后（Alembic fileConfig 会清掉已有处理器）。
      RotatingFileHandler 严格多进程安全需队列方案，本项目为单实例部署（见 README
      部署约束），直接轮转可接受。"""
    global _logging_configured
    if _logging_configured:
        return
    _logging_configured = True

    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    fmt = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, 'app.log'),
        maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(logging.WARNING)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)


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
    """为每个用户保证「寝室 / 活动」各有一条 is_default 配置套：
    某类型无套则建空默认套，有套无默认则提升该类型下最早的一条。
    配置套已按 task_type 类型化（dorm/activity），绑定与批量应用按类型过滤。"""
    try:
        with app.app_context():
            users = User.query.all()
            for u in users:
                for task_type, label in (('dorm', '寝室默认配置套'), ('activity', '活动默认配置套')):
                    default = ConfigSet.query.filter_by(user_id=u.id, is_default=True,
                                                        task_type=task_type).first()
                    if default:
                        continue
                    first = (ConfigSet.query.filter_by(user_id=u.id, task_type=task_type)
                             .order_by(ConfigSet.id.asc()).first())
                    if first:
                        first.is_default = True
                    else:
                        s = ConfigSet(user_id=u.id, name=label, is_default=True, task_type=task_type)
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
