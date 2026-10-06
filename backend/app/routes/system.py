# 系统信息蓝图：管理员查看运行状态（版本/环境/时长/数据库/用户统计），只读。
# 前缀 /api/system
import os
from datetime import datetime

from flask import Blueprint, current_app
from sqlalchemy import text

from app.extensions import db
from app.models.user import User, now_cst
from app.utils.auth import admin_required
from app.utils.response import success

bp = Blueprint('system', __name__, url_prefix='/api/system')

# 进程级启动时间：模块首次导入时刻，用于计算运行时长（近似应用启动时间）
STARTED_AT = now_cst()

# VERSION 文件位置候选（按序尝试）。system.py 位于 <root>/backend/app/routes/system.py：
#   here（routes 目录）向上三级 = 仓库根（本地开发；实测 routes→app→backend→Web端）
#   here 向上两级 = backend/（Docker 镜像内 WORKDIR /app，VERSION 由 Dockerfile 打入）
def _version_candidates():
    here = os.path.dirname(os.path.abspath(__file__))
    up = lambda n: os.path.normpath(os.path.join(here, *(['..'] * n)))
    return [os.path.join(up(3), 'VERSION'), os.path.join(up(2), 'VERSION')]


def _read_version():
    """按候选路径读取 VERSION；缺失时回退 unknown"""
    for path in _version_candidates():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception:
            continue
    return 'unknown'


@bp.route('/info', methods=['GET'])
@admin_required
def system_info():
    """
    系统信息汇总（设置页"系统信息"卡片数据源）：
      - version：仓库 VERSION 文件内容
      - env/debug：当前 Flask 运行环境
      - started_at/uptime_seconds：进程启动时间与已运行秒数
      - database：SELECT 1 探活结果
      - users：用户规模统计（总数/管理员/普通用户/启用/禁用）
    """
    # 数据库探活：任何异常都归为 unreachable，不让只读接口因数据库故障而 500
    db_ok = True
    try:
        db.session.execute(text('SELECT 1'))
    except Exception:
        db_ok = False

    total = User.query.count()
    info = {
        'version': _read_version(),
        'env': current_app.config.get('ENV', ''),
        'debug': bool(current_app.config.get('DEBUG')),
        'started_at': STARTED_AT.strftime('%Y-%m-%d %H:%M:%S'),
        'uptime_seconds': max(0, int((datetime.now() - STARTED_AT).total_seconds())),
        'server_time': now_cst().strftime('%Y-%m-%d %H:%M:%S'),
        'database': {'status': 'ok' if db_ok else 'unreachable'},
        'users': {
            'total': total,
            'admins': User.query.filter_by(role='admin').count(),
            'users': User.query.filter_by(role='user').count(),
            'enabled': User.query.filter_by(enabled=True).count(),
            'disabled': User.query.filter_by(enabled=False).count(),
        },
    }
    return success(info)
