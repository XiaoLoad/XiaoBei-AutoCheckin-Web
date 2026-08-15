# 用户领域服务：收纳路由可复用的数据查询 / 聚合片段，路由只做 HTTP 适配。
# 不做完整 service 框架，仅把跨路由复用的逻辑下沉，降低路由层厚度与重复。
from app.extensions import db
from app.models.user import User


def load_user(user_id):
    """按 user_id 取用户；不存在返回 None（调用方决定如何处理）"""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, uid)


def user_summary():
    """全表聚合，用于前端汇总卡片（总数 / 启用 / 禁用 / 额度使用）。"""
    total_users = User.query.count()
    enabled_count = User.query.filter_by(enabled=True).count()
    agg = db.session.query(db.func.sum(User.quota), db.func.sum(User.used_quota)).first()
    return {
        'total_users': total_users,
        'enabled': enabled_count,
        'disabled': total_users - enabled_count,
        'total_quota': int(agg[0] or 0),
        'used_quota': int(agg[1] or 0),
    }
