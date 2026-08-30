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
    """全表聚合，用于前端汇总卡片（总数 / 启用 / 禁用 / 额度使用）。
    已用额度按产品定义恒等于各用户的平台账号数，现算子查询聚合——
    存储 used_quota 计数器已被历史操作污染（如 admin=128/实际 0），不再可信。"""
    from app.models.b_account import BAccount

    total_users = User.query.count()
    enabled_count = User.query.filter_by(enabled=True).count()
    used_subq = (
        db.session.query(BAccount.user_id, db.func.count(BAccount.id).label('cnt'))
        .group_by(BAccount.user_id)
        .subquery()
    )
    used_total = db.session.query(
        db.func.coalesce(db.func.sum(used_subq.c.cnt), 0)
    ).select_from(used_subq).scalar()
    agg = db.session.query(db.func.sum(User.quota)).first()
    return {
        'total_users': total_users,
        'enabled': enabled_count,
        'disabled': total_users - enabled_count,
        'total_quota': int(agg[0] or 0),
        'used_quota': int(used_total or 0),
    }
