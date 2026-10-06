# 「我的调度状态 / 我的推送送达」端点回归（me/overview 新增的两个聚合）：
# 核心红线——数据严格限本人：
#   ① scheduler 聚合：jobCount/nextRuns 只统计本人 schedule 的 job，他人任务不可见；
#   ② push 聚合：分母只含真实发送（attempts>0），跳过单列不计入分母（口径对齐管理员侧）；
#   ③ 其他用户的 PushLog / SignRecord 不得出现在本人的统计与明细里。
# 调度器在测试环境 SCHEDULER_ENABLED=0：get_scheduler() 返回未启动实例（get_jobs 为空），
# running=False、jobCount=0 是预期行为；job 级数据（nextRuns）由管理员侧链路覆盖。
from app.extensions import db
from app.models import BAccount, PushLog, Schedule, SignRecord, User
from app.models.user import now_cst
from app.utils.auth import generate_token


def _seed_user(tag):
    uname = f'tc_ms_{tag}_{now_cst().strftime("%H%M%S%f")}'
    u = User(username=uname, role='user', enabled=True, quota=100)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    acc = BAccount(user_id=u.id, account=f'ms_acc_{tag}', password_enc='x')
    acc.set_profile({'name': f'姓名{tag}'})
    db.session.add(acc)
    db.session.flush()
    s = Schedule(user_id=u.id, account_id=acc.id, task_type='dorm', enabled=True)
    s.set_config({'stub': True})
    db.session.add(s)
    db.session.commit()
    headers = {'Authorization': f'Bearer {generate_token(u)}'}
    return u, acc, headers


def _cleanup(u):
    PushLog.query.filter_by(user_id=u.id).delete()
    SignRecord.query.filter_by(user_id=u.id).delete()
    Schedule.query.filter_by(user_id=u.id).delete()
    BAccount.query.filter_by(user_id=u.id).delete()
    db.session.delete(u)
    db.session.commit()


def test_scheduler_section_scoped_to_self(app, app_ctx):
    """scheduler 子结构存在且任务计数只含本人；调度器未启动时 running=False、无 job。"""
    c = app.test_client()
    u, _, headers = _seed_user('a')
    try:
        data = c.get('/api/me/overview', headers=headers).get_json()['data']
        sch = data['scheduler']
        assert sch['running'] is False          # 测试环境 SCHEDULER_ENABLED=0
        assert sch['jobCount'] == 0
        assert sch['nextRuns'] == []
        assert sch['taskTypes'] == {'dorm': 1, 'activity': 0}
        assert sch['lastRunAt'] == ''
    finally:
        _cleanup(u)


def test_push_scoped_to_self_and_rate_excludes_skips(app, app_ctx):
    """本人推送统计只算自己的 PushLog；跳过类不计入成功率分母；明细仅含本人记录。"""
    c = app.test_client()
    u1, acc1, h1 = _seed_user('u1')
    u2, acc2, h2 = _seed_user('u2')
    try:
        rec1 = SignRecord(user_id=u1.id, account_id=acc1.id, sign_date=now_cst().date(),
                          status='success', task_type='dorm')
        rec2 = SignRecord(user_id=u2.id, account_id=acc2.id, sign_date=now_cst().date(),
                          status='success', task_type='dorm')
        db.session.add_all([rec1, rec2])
        db.session.flush()
        db.session.add_all([
            # u1：1 成功 + 1 真失败 + 1 跳过
            PushLog(user_id=u1.id, account_id=acc1.id, sign_record_id=rec1.id,
                    channel='serverchan', ok=True, attempts=1),
            PushLog(user_id=u1.id, account_id=acc1.id, sign_record_id=rec1.id,
                    channel='pushplus', ok=False, attempts=2,
                    error='PushPlus 推送被拒（code=400，message=bad）'),
            PushLog(user_id=u1.id, account_id=acc1.id, sign_record_id=rec1.id,
                    channel='email', ok=False, attempts=0,
                    error='已跳过：该账号未绑定此通道的推送凭证'),
            # u2：1 成功——绝不能算进 u1 的任何统计
            PushLog(user_id=u2.id, account_id=acc2.id, sign_record_id=rec2.id,
                    channel='serverchan', ok=True, attempts=1),
        ])
        db.session.commit()

        d1 = c.get('/api/me/overview', headers=h1).get_json()['data']['pushHealth']
        s1 = d1['summary']
        assert s1['sent'] == 2          # 3 行中 2 行真发出
        assert s1['ok'] == 1
        assert s1['fail'] == 1          # 跳过不算失败
        assert s1['skipped'] == 1
        assert s1['rate'] == 50         # 分母 2（不含跳过）
        # u1 两条未送达都该被抓出：pushplus 真失败 + email 跳过（均发生在成功的签到上）
        assert d1['signOkPushFail']['total'] == 2
        items1 = d1['signOkPushFail']['list']
        assert items1[0]['skipped'] is False and items1[0]['channel'] == 'pushplus'  # 真失败在前
        assert items1[1]['skipped'] is True and items1[1]['channel'] == 'email'
        assert all(it['account'] == 'ms_acc_u1' for it in items1)  # 明细仅本人账号

        d2 = c.get('/api/me/overview', headers=h2).get_json()['data']['pushHealth']
        assert d2['summary']['sent'] == 1 and d2['summary']['ok'] == 1
        assert d2['summary']['rate'] == 100
        assert d2['signOkPushFail']['total'] == 0   # u2 的推送全部送达
    finally:
        _cleanup(u1)
        _cleanup(u2)


def test_push_skipped_only_show_amber_not_danger(app, app_ctx):
    """只有跳过类未送达时状态为 amber（配置问题），有真失败才升 danger（通道故障）。"""
    c = app.test_client()
    u, acc, headers = _seed_user('s')
    try:
        rec = SignRecord(user_id=u.id, account_id=acc.id, sign_date=now_cst().date(),
                         status='success', task_type='dorm')
        db.session.add(rec)
        db.session.flush()
        db.session.add(PushLog(user_id=u.id, account_id=acc.id, sign_record_id=rec.id,
                               channel='email', ok=False, attempts=0,
                               error='已跳过：该账号未绑定此通道的推送凭证'))
        db.session.commit()

        data = c.get('/api/me/overview', headers=headers).get_json()['data']['pushHealth']
        assert data['summary']['sent'] == 0
        assert data['summary']['skipped'] == 1
        assert data['summary']['rate'] is None      # 无真实发送，不表态
    finally:
        _cleanup(u)
