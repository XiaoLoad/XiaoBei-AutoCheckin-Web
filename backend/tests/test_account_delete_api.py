# 删除账号级联回归：账号下任务已执行过（sign_records.schedule_id 引用任务）时，
# 删账号必须成功。历史缺陷：先删 schedules 后删 sign_records，触发 MySQL 1451 外键拦截。
from app.extensions import db
from app.models import BAccount, Schedule, SignRecord
from app.models.user import now_cst


def _seed_account_with_executed_task():
    """ORM 直建 账号 + 任务 + 引用任务的签到记录（绕过 B 平台校验，聚焦级联顺序）"""
    from app.models.user import User

    u = User.query.filter_by(username='tc_user').first()
    acc = BAccount.query.filter_by(user_id=u.id, account='tc_del_acc').first()
    if not acc:
        acc = BAccount(user_id=u.id, account='tc_del_acc')
        acc.set_password('pw')
        db.session.add(acc)
        db.session.commit()
    s = Schedule.query.filter_by(account_id=acc.id, task_type='dorm').first()
    if not s:
        s = Schedule(user_id=u.id, account_id=acc.id, task_type='dorm', mode='custom',
                     custom_json='{"hour":8,"minute":0,"weekdays":[1]}')
        db.session.add(s)
        db.session.commit()
    if not SignRecord.query.filter_by(account_id=acc.id, schedule_id=s.id).first():
        db.session.add(SignRecord(
            user_id=u.id, account_id=acc.id, schedule_id=s.id,
            task_name='寝室签到', task_type='dorm',
            sign_date=now_cst().date(), signed_at=now_cst(), status='success',
        ))
        db.session.commit()
    return acc, s


def test_delete_account_with_executed_tasks(app, user_headers):
    acc, sched = _seed_account_with_executed_task()
    c = app.test_client()

    r = c.delete(f'/api/accounts/{acc.id}', headers=user_headers)
    assert r.status_code == 200

    # 记录/任务/账号全部清理，调度器 job 同步移除（由路由内 sched_ids 循环处理）
    assert db.session.get(BAccount, acc.id) is None
    assert db.session.get(Schedule, sched.id) is None
    assert SignRecord.query.filter_by(account_id=acc.id).count() == 0


def test_delete_account_without_records_still_works(app, user_headers):
    """无执行记录的账号（从未跑过任务）删除不受影响"""
    from app.models.user import User

    u = User.query.filter_by(username='tc_user').first()
    acc = BAccount.query.filter_by(user_id=u.id, account='tc_del_acc2').first()
    if not acc:
        acc = BAccount(user_id=u.id, account='tc_del_acc2')
        acc.set_password('pw')
        db.session.add(acc)
        db.session.commit()
    c = app.test_client()
    r = c.delete(f'/api/accounts/{acc.id}', headers=user_headers)
    assert r.status_code == 200
    assert db.session.get(BAccount, acc.id) is None
