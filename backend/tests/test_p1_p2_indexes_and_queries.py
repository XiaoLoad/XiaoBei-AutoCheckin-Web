# P1+P2 优化回归：外键索引迁移与查询模式改写。
# 查询改写最怕「优化完结果变了」，故每条用例都锚定业务语义而非实现：
# 批量聚合必须与逐组 COUNT 一致、success 选取口径不回退、引用计数不因只取部分列而漏算。
import uuid

import pytest

from app.extensions import db
from app.models import (BAccount, PoolCredential, PushGroup, PushGroupDigestLog,
                        PushGroupMember, SignRecord, User)
from app.models.user import now_cst


@pytest.fixture()
def env(app_ctx):
    """唯一用户 + 两个寝室分组（成员数不同）+ 账号，用后清场。
    push_group_members 有 (group_id, account_id) 唯一约束，成员数差异靠多账号实现。"""
    uname = f'tc_p1p2_{uuid.uuid4().hex[:10]}'
    u = User(username=uname, role='user', enabled=True, quota=100, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    accs = [BAccount(user_id=u.id, account=f'acc{i}_{uname}', password_enc='x')
            for i in range(3)]
    db.session.add_all(accs)
    db.session.flush()
    g1 = PushGroup(user_id=u.id, type=PushGroup.TYPE_DORM, name='507')
    g2 = PushGroup(user_id=u.id, type=PushGroup.TYPE_DORM, name='508')
    db.session.add_all([g1, g2])
    db.session.flush()
    for a in accs:
        db.session.add(PushGroupMember(group_id=g1.id, account_id=a.id))
    db.session.add(PushGroupMember(group_id=g2.id, account_id=accs[0].id))
    db.session.commit()

    uid, g1id, g2id = u.id, g1.id, g2.id
    yield {'uid': uid, 'acc_id': accs[0].id, 'accs': [a.id for a in accs],
           'g1': g1id, 'g2': g2id}

    PushGroupDigestLog.query.filter(PushGroupDigestLog.group_id.in_([g1id, g2id])) \
        .delete(synchronize_session=False)
    PushGroupMember.query.filter(PushGroupMember.group_id.in_([g1id, g2id])) \
        .delete(synchronize_session=False)
    PushGroup.query.filter_by(user_id=uid).delete(synchronize_session=False)
    SignRecord.query.filter_by(user_id=uid).delete(synchronize_session=False)
    # class LIKE 用例会往本用户名下加账号与凭证，须一并清掉，否则残留行会让
    # 后续用例的计数断言翻倍（已验证 ESCAPE 语义正常，脏数据才是假失败来源）
    PoolCredential.query.filter_by(user_id=uid).delete(synchronize_session=False)
    BAccount.query.filter_by(user_id=uid).delete(synchronize_session=False)
    db.session.delete(db.session.get(User, uid))
    db.session.commit()


# ───────────────────────── P1：外键索引存在 ─────────────────────────

def test_fk_indexes_exist(app_ctx):
    """迁移 b7c8d9e0f1a2 的三个外键索引必须真实存在于库中（防止迁移漏跑/被误删）。"""
    from sqlalchemy import inspect
    insp = inspect(db.engine)

    def _indexed_cols(table):
        cols = set()
        for idx in insp.get_indexes(table):
            if len(idx['column_names']) == 1:
                cols.add(idx['column_names'][0])
        return cols

    assert 'schedule_id' in _indexed_cols('sign_records')
    assert 'config_set_id' in _indexed_cols('schedules')
    assert 'location_id' in _indexed_cols('config_sets')


# ───────────────────────── P2.1：分组列表批量聚合 ─────────────────────────

def test_batch_member_counts_match_per_group_count(env):
    """批量 GROUP BY 聚合与逐组 COUNT 结果一致（优化不改变 memberCount 语义）。"""
    from app.routes.group_push import _batch_member_counts, _member_count
    counts = _batch_member_counts([env['g1'], env['g2']])
    assert counts[env['g1']] == _member_count(db.session.get(PushGroup, env['g1'])) == 3
    assert counts[env['g2']] == _member_count(db.session.get(PushGroup, env['g2'])) == 1
    assert _batch_member_counts([]) == {}


def test_batch_today_status_matches_single_query(env):
    """今日状态批量 IN 取回与单组查询一致；无 log 的组不在映射里（前端显示未推送）。"""
    from app.routes.group_push import _batch_today_status, _today_status
    today = now_cst().date()
    db.session.add(PushGroupDigestLog(group_id=env['g1'], date=today, status='success',
                                      member_total=3, member_done=3))
    db.session.commit()
    got = _batch_today_status([env['g1'], env['g2']])
    assert got[env['g1']]['status'] == 'success'
    assert got[env['g1']] == _today_status(env['g1'])
    assert env['g2'] not in got


def test_class_member_like_escapes_wildcards(env):
    """班级名含 %/_ 时不得被当成 LIKE 通配符：'100%班' 不能匹配到 '100xy班'。
    断言只看本 fixture 用户名下的账号（全表计数会被并行/历史残留数据污染）。"""
    from app.routes.group_push import _member_count
    uid = env['uid']
    db.session.add_all([
        BAccount(user_id=uid, account='acc_pct', password_enc='x', enabled=True,
                 profile_json='{"className": "100%班"}'),
        BAccount(user_id=uid, account='acc_us', password_enc='x', enabled=True,
                 profile_json='{"className": "A_B班"}'),
        BAccount(user_id=uid, account='acc_x', password_enc='x', enabled=True,
                 profile_json='{"className": "100xy班"}'),
    ])
    db.session.commit()

    pct = PushGroup(user_id=uid, type=PushGroup.TYPE_CLASS, name='100%班')
    us = PushGroup(user_id=uid, type=PushGroup.TYPE_CLASS, name='A_B班')
    db.session.add_all([pct, us])
    db.session.commit()
    # 关键断言：若 % 未转义，'100%班' 的 LIKE 会吞掉 '100xy班'，计数变成 2
    assert _member_count(pct) == 1, '% 必须按字面匹配，不能吞掉 100xy班'
    assert _member_count(us) == 1, '_ 必须按字面匹配，不能匹配 Axy班'


# ───────────────────────── P2.3：成员记录一次查询选取 ─────────────────────────

def test_member_records_picks_latest_success(env, app_ctx):
    """选取口径不回退：同账号多条记录时 success 优先（取最新 success），无 success 取最新一条。"""
    from app.services.group_digest import _member_records
    uid, aid, today = env['uid'], env['acc_id'], now_cst().date()
    db.session.add_all([
        SignRecord(user_id=uid, account_id=aid, sign_date=today, task_type='dorm',
                   status='fail', fail_reason='超时'),
        SignRecord(user_id=uid, account_id=aid, sign_date=today, task_type='dorm',
                   status='success'),
        SignRecord(user_id=uid, account_id=aid, sign_date=today, task_type='dorm',
                   status='fail', fail_reason='二次重试又失败'),
    ])
    db.session.commit()

    rows = _member_records([aid], today)
    assert len(rows) == 1
    acc, rec = rows[0]
    assert acc.id == aid
    assert rec.status == 'success', '有 success 时必须选 success（哪怕不是最新一条）'

    # 无 success：取最新一条
    SignRecord.query.filter(SignRecord.account_id == aid,
                            SignRecord.status == 'success') \
        .delete(synchronize_session=False)
    db.session.commit()
    _, rec = _member_records([aid], today)[0]
    assert rec.status == 'fail' and rec.fail_reason == '二次重试又失败'

    # 全天无记录：返回 None 而非抛错
    SignRecord.query.filter_by(account_id=aid).delete(synchronize_session=False)
    db.session.commit()
    _, rec = _member_records([aid], today)[0]
    assert rec is None


# ───────────────────────── P2.2：凭证引用计数只取所需列 ─────────────────────────

def test_acc_cred_ref_count_reads_push_cred_json(env):
    """引用计数从 (id, push_cred_json) 元组统计：漏算会让凭证删掉后留下悬空绑定。"""
    from app.routes.pools import _acc_cred_ref_count
    uid = env['uid']
    cred = PoolCredential(user_id=uid, channel='serverchan', name='t',
                          secret_enc='x', enabled=True)
    db.session.add(cred)
    db.session.commit()
    acc = db.session.get(BAccount, env['acc_id'])
    acc.set_push_creds({'serverchan': cred.id})
    db.session.commit()

    rows = db.session.query(BAccount.id, BAccount.push_cred_json).all()
    assert _acc_cred_ref_count(rows, cred.id) == 1
    assert _acc_cred_ref_count(rows, cred.id + 99999) == 0
