# 用户真删除回归：接口曾是桩（返回成功但不删数据、前端靠本地隐藏 id 假装删掉），
# 转真后两条风险最高：① 级联顺序（除 push_group_* / op_anomaly_acks 外全是 RESTRICT 外键，
# 顺序错就抛 1451，且半途失败会留下「用户还在、数据没了一半」）；② 审计日志必须活下来。
import pytest
from sqlalchemy import text

from app.extensions import db
from app.models import (ActivityWindow, BAccount, ConfigSet, ImageGroup, JwAccount,
                        JwTimetable, PoolCredential, PoolImage, PoolLocation, PoolUa,
                        PushGroup, PushGroupMember, PushLog, Schedule, SignRecord, User)
from app.models.op_log import OpLog
from app.models.user import now_cst

TAG = 'tc_purge'
# 清理用的删序（子 → 父），与 purge_user 相互独立：被测功能坏了也要能收干净现场
_PURGE_SQL = (
    "DELETE aw FROM activity_windows aw JOIN schedules s ON s.id = aw.schedule_id WHERE s.user_id = :uid",
    "DELETE FROM push_logs WHERE user_id = :uid",
    "DELETE FROM sign_records WHERE user_id = :uid",
    "DELETE FROM push_group_members WHERE group_id IN (SELECT id FROM push_groups WHERE user_id = :uid)",
    "DELETE FROM push_groups WHERE user_id = :uid",
    "DELETE FROM jw_timetables WHERE b_account_id IN (SELECT id FROM b_accounts WHERE user_id = :uid)",
    "DELETE FROM jw_accounts WHERE b_account_id IN (SELECT id FROM b_accounts WHERE user_id = :uid)",
    "DELETE FROM schedules WHERE user_id = :uid",
    "DELETE FROM b_accounts WHERE user_id = :uid",
    "DELETE FROM config_sets WHERE user_id = :uid",
    "DELETE FROM pool_images WHERE user_id = :uid",
    "DELETE FROM image_groups WHERE user_id = :uid",
    "DELETE FROM pool_locations WHERE user_id = :uid",
    "DELETE FROM pool_uas WHERE user_id = :uid",
    "DELETE FROM pool_credentials WHERE user_id = :uid",
    "UPDATE op_logs SET user_id = NULL WHERE user_id = :uid",
    "DELETE FROM users WHERE id = :uid",
)


def _hard_cleanup():
    """按用户名前缀收尾：先撤掉可能引用这些用户的**测试账号**配置套，再按删序清库。
    引用清理限定在 tc_ 前缀的账号上——绝不能波及真实用户的配置。"""
    rows = User.query.filter(User.username.like(f'{TAG}%')).all()
    ua_ids = {ua.id for u in rows for ua in PoolUa.query.filter_by(user_id=u.id).all()}
    if ua_ids:
        for cs in ConfigSet.query.all():
            owner = db.session.get(User, cs.user_id)
            if owner is None or not owner.username.startswith('tc_'):
                continue
            if ((cs.config or {}).get('advanced') or {}).get('uaTemplateId') in ua_ids:
                db.session.delete(cs)
        db.session.commit()
    for u in rows:
        for sql in _PURGE_SQL:
            db.session.execute(text(sql), {'uid': u.id})
    # 审计行按操作者前缀清（纪律同 test_op_logs.audit_cleanup）：本文件会造 auth.login
    # 历史行与 tc_admin 的 user.delete 行，不清就会在开发库的审计表里越积越多
    OpLog.query.filter(OpLog.username.like('tc_%')).delete(synchronize_session=False)
    db.session.commit()


@pytest.fixture()
def make_user(app_ctx):
    """惰性创建测试用户，用例结束无条件收干净（无论断言成功与否）。
    依赖 app_ctx 让整个用例期间保持应用上下文可用（本文件多处直接读写库）。"""
    def _make(suffix, role='user'):
        _hard_cleanup()
        u = User(username=f'{TAG}_{suffix}', role=role, enabled=True, quota=100, used_quota=0)
        u.set_password('pw-' + suffix)
        db.session.add(u)
        db.session.commit()
        return u

    yield _make
    _hard_cleanup()


def _seed_everything(user):
    """把该用户名下所有会被级联清掉的表都铺一行，返回关键 id 供断言"""
    acc = BAccount(user_id=user.id, account=f'{user.username}_acc')
    acc.set_password('pw')
    db.session.add(acc)
    db.session.commit()

    sched = Schedule(user_id=user.id, account_id=acc.id, task_type='dorm', mode='custom',
                     custom_json='{"hour":8,"minute":0,"weekdays":[1]}')
    db.session.add(sched)
    db.session.commit()

    rec = SignRecord(user_id=user.id, account_id=acc.id, schedule_id=sched.id,
                     task_name='寝室签到', task_type='dorm',
                     sign_date=now_cst().date(), signed_at=now_cst(), status='success')
    db.session.add(rec)
    db.session.commit()

    db.session.add(PushLog(user_id=user.id, account_id=acc.id, schedule_id=sched.id,
                           sign_record_id=rec.id, channel='serverchan', ok=True))
    # activity_windows 没有 user_id，只靠 schedule_id 归属，故用 schedule 断言它的清理
    db.session.add(ActivityWindow(schedule_id=sched.id, date=now_cst().date(),
                                  start_at=now_cst(), end_at=now_cst()))
    db.session.add(ConfigSet(user_id=user.id, name=f'{TAG} 配置套', task_type='dorm'))
    group = PushGroup(user_id=user.id, type=PushGroup.TYPE_DORM, name=f'{TAG} 分组')
    db.session.add(group)
    db.session.commit()
    db.session.add(PushGroupMember(group_id=group.id, account_id=acc.id))
    img_group = ImageGroup(user_id=user.id, name=f'{TAG} 图库')
    db.session.add(img_group)
    db.session.commit()
    db.session.add(PoolImage(user_id=user.id, group_id=img_group.id))
    db.session.add(PoolLocation(user_id=user.id, name=f'{TAG} 位置', is_system=False))
    db.session.add(PoolUa(user_id=user.id, content='Mozilla/5.0 (probe)', is_system=True))
    db.session.add(PoolCredential(user_id=user.id, channel='serverchan',
                                  name=f'{TAG} 凭证', secret_enc='enc'))
    db.session.add(JwAccount(b_account_id=acc.id, student_no='20260001', password_enc='enc'))
    db.session.add(JwTimetable(b_account_id=acc.id, semester='2026-2027-1', entries_json='[]'))
    db.session.commit()
    return acc, sched


def _counts_for(uid, table, column='user_id'):
    return db.session.execute(text(f'SELECT COUNT(*) FROM {table} WHERE {column} = :uid'),
                              {'uid': uid}).scalar()


def test_delete_user_purges_all_owned_rows(app, admin_headers, make_user):
    u = make_user('full')
    acc, sched = _seed_everything(u)
    uid, acc_id, sched_id = u.id, acc.id, sched.id

    r = app.test_client().delete(f'/api/users/{uid}', headers=admin_headers)
    assert r.status_code == 200, r.get_json()

    assert db.session.get(User, uid) is None
    for table in ('b_accounts', 'schedules', 'sign_records', 'push_logs',
                  'config_sets', 'push_groups', 'pool_images', 'image_groups',
                  'pool_locations', 'pool_uas', 'pool_credentials'):
        assert _counts_for(uid, table) == 0, f'{table} 未清干净'
    # 无 user_id 的表按外键归属断言
    assert _counts_for(sched_id, 'activity_windows', 'schedule_id') == 0
    assert _counts_for(acc_id, 'push_group_members', 'account_id') == 0
    assert _counts_for(acc_id, 'jw_accounts', 'b_account_id') == 0
    assert _counts_for(acc_id, 'jw_timetables', 'b_account_id') == 0
    assert db.session.get(Schedule, sched_id) is None


def test_delete_user_keeps_audit_rows(app, admin_headers, make_user):
    u = make_user('audit')
    # 历史审计：该用户自己操作产生的日志，删除后必须仍在、且只解外键
    db.session.add(OpLog(user_id=u.id, username=u.username, role='user', action='auth.login',
                         category='auth', summary='登录成功', ip='127.0.0.1'))
    db.session.commit()
    uid = u.id

    r = app.test_client().delete(f'/api/users/{uid}', headers=admin_headers)
    assert r.status_code == 200

    kept = OpLog.query.filter_by(action='auth.login', username=f'{TAG}_audit').all()
    assert len(kept) == 1, '历史审计行被连带删除了'
    assert kept[0].user_id is None, '外键未解开，留着悬空 user_id'
    # 删除动作本身的日志：记的是操作者（管理员），被删对象落在 detail
    row = (OpLog.query.filter_by(action='user.delete')
           .order_by(OpLog.id.desc()).first())
    assert row is not None and row.username == 'tc_admin'
    assert f'{TAG}_audit' in (row.summary or '')
    assert '未实际销毁' not in (row.summary or ''), '桩文案没清掉'
    assert 'stub' not in (row.detail or '')


def test_delete_self_refused(app, make_user):
    """删自己会当场失去会话，属防呆：接口对当前登录账号直接拒绝"""
    from app.utils.auth import generate_token

    u = make_user('self', role='admin')
    headers = {'Authorization': f'Bearer {generate_token(u)}'}
    r = app.test_client().delete(f'/api/users/{u.id}', headers=headers)
    assert r.status_code == 403
    assert '不能删除当前登录' in r.get_json()['message']
    assert db.session.get(User, u.id) is not None


def test_delete_last_admin_refused(app, admin_headers, make_user, monkeypatch):
    """最后一个管理员不可删——否则再没人能登录管理端。
    开发库里管理员不止一个，故把计数压到 1（只替这一处判断，不碰真实数据）。"""
    import app.routes.users as users_route

    class _OnlyOneAdmin:
        class query:
            @staticmethod
            def filter_by(**kwargs):
                return _OnlyOneAdmin.query

            @staticmethod
            def count():
                return 1

    u = make_user('lastadmin', role='admin')
    monkeypatch.setattr(users_route, 'User', _OnlyOneAdmin)
    r = app.test_client().delete(f'/api/users/{u.id}', headers=admin_headers)
    assert r.status_code == 403
    assert '至少保留一个管理员' in r.get_json()['message']
    assert db.session.get(User, u.id) is not None


def test_delete_blocked_when_shared_resource_referenced(app, admin_headers, make_user, user_headers):
    """他人配置套引用的 UA 模板必须拦下：UA 引用存在 JSON 里，数据库拦不住。
    拒绝时不能有任何副作用（连自己的账号都不该被删掉）。"""
    victim = make_user('blocked')
    _seed_everything(victim)
    ua = PoolUa.query.filter_by(user_id=victim.id).first()

    owner = User.query.filter_by(username='tc_user').first()
    cs = ConfigSet(user_id=owner.id, name=f'{TAG} 外来套', task_type='dorm')
    cs.set_config({'advanced': {'uaTemplateId': ua.id}})
    db.session.add(cs)
    db.session.commit()

    r = app.test_client().delete(f'/api/users/{victim.id}', headers=admin_headers)
    assert r.status_code == 409, r.get_json()
    body = r.get_json()
    assert 'UA 模板' in body['message']
    assert body['data']['blockers'][0]['kind'] == 'ua'

    assert db.session.get(User, victim.id) is not None
    assert db.session.get(PoolUa, ua.id) is not None
    assert _counts_for(victim.id, 'b_accounts') == 1, '被拒时不该删掉任何数据'
