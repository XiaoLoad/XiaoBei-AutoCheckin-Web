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


def user_delete_blockers(user):
    """删除用户前的「他人引用」体检，返回阻断项列表（空 = 可删）。

    只有共享资源会被别人引用：`is_system` 的位置/UA/凭证模板，以及可能被他人分组
    收纳的账号。私有资源不可能被引用——可见性规则决定别人根本看不到它们。

    两类引用必须分别查，因为只有一类会被数据库拦下：
      - 位置是外键引用（`config_sets.location_id`），漏查时 DELETE 会抛 1451；
      - UA 与推送凭证的引用存在**配置体的 JSON 里**（`advanced.uaTemplateId`、
        `push.credIds`）以及账号级绑定 `b_accounts.push_cred_json`，数据库完全拦不住，
        漏查的后果是别人的定时任务在删除后静默失去 UA / 推送凭证。

    与 `pools.py` 的单条删除口径一致：被引用就拒绝，不替用户决定删掉别人的配置。
    """
    from app.models.b_account import BAccount, binding_cred_id
    from app.models.config_set import ConfigSet
    from app.models.group_push import PushGroup, PushGroupMember
    from app.models.pools import PoolCredential, PoolLocation, PoolUa

    blockers = []

    loc_ids = [row.id for row in PoolLocation.query.filter_by(user_id=user.id).all()]
    if loc_ids:
        refs = ConfigSet.query.filter(ConfigSet.location_id.in_(loc_ids),
                                      ConfigSet.user_id != user.id).count()
        if refs:
            blockers.append({'kind': 'location', 'label': '位置', 'refs': refs})

    ua_rows = PoolUa.query.filter_by(user_id=user.id).all()
    cred_rows = PoolCredential.query.filter_by(user_id=user.id).all()
    if ua_rows or cred_rows:
        others = ConfigSet.query.filter(ConfigSet.user_id != user.id).all()
        other_accs = BAccount.query.filter(BAccount.user_id != user.id).all()
        ua_refs = sum(1 for cs in others for ua in ua_rows
                      if ((cs.config or {}).get('advanced') or {}).get('uaTemplateId') == ua.id)
        if ua_refs:
            blockers.append({'kind': 'ua', 'label': 'UA 模板', 'refs': ua_refs})
        cred_ids = {c.id for c in cred_rows}
        cred_refs = sum(1 for cs in others
                        if cred_ids & set((((cs.config or {}).get('push') or {}).get('credIds') or {}).values()))
        cred_refs += sum(1 for a in other_accs
                         if cred_ids & {binding_cred_id(v) for v in (a.push_creds or {}).values()})
        if cred_refs:
            blockers.append({'kind': 'credential', 'label': '推送凭证', 'refs': cred_refs})

    acc_ids = [row.id for row in BAccount.query.filter_by(user_id=user.id).all()]
    if acc_ids:
        refs = (PushGroupMember.query
                .join(PushGroup, PushGroup.id == PushGroupMember.group_id)
                .filter(PushGroupMember.account_id.in_(acc_ids),
                        PushGroup.user_id != user.id).count())
        if refs:
            blockers.append({'kind': 'group_member', 'label': '他人分组收录的账号', 'refs': refs})
    return blockers


def purge_user(user):
    """真删除用户：把名下私有数据全部清掉，返回级联计数。

    顺序即依赖关系，**不能随意调整**：核心库里除 `push_group_*` 与 `op_anomaly_acks`
    声明了级联外，其余外键都是 RESTRICT，顺序错了会抛 1451；而删除是单事务，
    半途失败会留下「用户还在、数据没了一半」的残局。顺序的约束链：
      push_logs → sign_records/schedules/b_accounts；
      sign_records、activity_windows、jw_timetables、jw_accounts → schedules / b_accounts；
      schedules → config_sets / b_accounts；config_sets → pool_locations；
      pool_images → image_groups。

    审计日志刻意**不删**：`op_logs` 里那些行记的是「谁做过什么」，用户被删后
    仍是追责依据（username 本来就是快照），故只把 `user_id` 置空以解开外键。
    `jw_semesters` 是学校级共享数据，不属于任何用户，不在此列。
    """
    from app.models.b_account import BAccount
    from app.models.config_set import ConfigSet
    from app.models.group_push import (PushGroup, PushGroupDigestLog,
                                       PushGroupDigestPending, PushGroupMember)
    from app.models.jwxt import ActivityWindow, JwAccount, JwTimetable
    from app.models.op_log import OpLog
    from app.models.pools import (ImageGroup, PoolCredential, PoolImage,
                                  PoolLocation, PoolUa)
    from app.models.push_log import PushLog
    from app.models.schedule import Schedule
    from app.models.sign_record import SignRecord

    def _ids(model):
        return [row.id for row in model.query.filter_by(user_id=user.id).all()]

    schedule_ids = _ids(Schedule)
    account_ids = _ids(BAccount)
    group_ids = _ids(PushGroup)

    counts = {}
    if schedule_ids:
        counts['activityWindows'] = ActivityWindow.query.filter(
            ActivityWindow.schedule_id.in_(schedule_ids)).delete(synchronize_session=False)
    counts['pushLogs'] = PushLog.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    counts['signRecords'] = SignRecord.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    if group_ids:
        # 两张摘要表模型里写了 CASCADE，仍显式删一遍：迁移若没带上该规则，
        # 靠数据库就会在 push_groups 上抛 1451
        PushGroupDigestPending.query.filter(PushGroupDigestPending.group_id.in_(group_ids)).delete(
            synchronize_session=False)
        PushGroupDigestLog.query.filter(PushGroupDigestLog.group_id.in_(group_ids)).delete(
            synchronize_session=False)
    member_q = PushGroupMember.query
    if group_ids or account_ids:
        member_q = member_q.filter(db.or_(PushGroupMember.group_id.in_(group_ids or [-1]),
                                          PushGroupMember.account_id.in_(account_ids or [-1])))
        counts['groupMembers'] = member_q.delete(synchronize_session=False)
    if account_ids:
        JwTimetable.query.filter(JwTimetable.b_account_id.in_(account_ids)).delete(
            synchronize_session=False)
        JwAccount.query.filter(JwAccount.b_account_id.in_(account_ids)).delete(
            synchronize_session=False)
    counts['groups'] = PushGroup.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    counts['schedules'] = Schedule.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    counts['accounts'] = BAccount.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    counts['configSets'] = ConfigSet.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    # 图库图片先于图库本身：pool_images.group_id 是指向 image_groups 的外键
    counts['images'] = PoolImage.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    counts['imageGroups'] = ImageGroup.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    counts['locations'] = PoolLocation.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    counts['uas'] = PoolUa.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    counts['credentials'] = PoolCredential.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    # 审计留痕：只解外键，不删行（删除动作本身的那条日志由订阅者在 commit 后写入）
    OpLog.query.filter_by(user_id=user.id).update({'user_id': None}, synchronize_session=False)
    db.session.delete(user)
    db.session.commit()
    return {'counts': counts, 'scheduleIds': schedule_ids}

