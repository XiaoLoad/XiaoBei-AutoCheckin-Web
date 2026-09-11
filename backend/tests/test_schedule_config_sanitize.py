# 任务配置入口 sanitize 回归：PUT /api/schedules 写 config_json 必须与配置套同一套
# 结构清洗——只放行已知顶层键，杜绝任务侧成为绕过 config_schema 的脏数据入口
import pytest

from app.extensions import db
from app.models import BAccount, Schedule


def _ensure_account():
    from app.models.user import User
    u = User.query.filter_by(username='tc_user').first()
    acc = BAccount.query.filter_by(user_id=u.id, account='tc_sched_acc').first()
    if not acc:
        acc = BAccount(user_id=u.id, account='tc_sched_acc')
        acc.set_password('pw')
        db.session.add(acc)
        db.session.commit()
    return acc


def _create_schedule(c, headers, acc):
    r = c.post('/api/schedules', json={'accountId': acc.id, 'taskType': 'dorm'}, headers=headers)
    return r.get_json()['data']['id']


@pytest.fixture()
def sched_cleanup():
    """记录用例创建的任务 id，结束按外键顺序删除。
    tc_sched_acc 为幂等复用账号保留；任务若不清理会污染持久用户 tc_user，
    导致按字母序后跑的 test_schedules_api 在全量运行下断言失败。"""
    created = []
    yield created
    from app.models import SignRecord
    for sid in created:
        SignRecord.query.filter_by(schedule_id=sid).delete()
        Schedule.query.filter_by(id=sid).delete()
    db.session.commit()


def test_config_with_unknown_top_key_rejected(app, user_headers, sched_cleanup):
    acc = _ensure_account()
    c = app.test_client()
    sid = _create_schedule(c, user_headers, acc)
    sched_cleanup.append(sid)
    r = c.put(f'/api/schedules/{sid}',
              json={'config': {'time': {'weekdays': [1], 'signTime': {'hour': 8, 'minute': 0}},
                               'image': {}, 'push': {}, 'advanced': {}, 'evilKey': 'x'}},
              headers=user_headers)
    assert r.status_code == 400
    assert r.get_json()['code'] == 4415


def test_config_missing_time_weekdays_rejected(app, user_headers, sched_cleanup):
    acc = _ensure_account()
    c = app.test_client()
    sid = _create_schedule(c, user_headers, acc)
    sched_cleanup.append(sid)
    r = c.put(f'/api/schedules/{sid}',
              json={'config': {'remarks': ['x'], 'image': {}, 'push': {}, 'advanced': {}}},
              headers=user_headers)
    assert r.status_code == 400
    assert r.get_json()['code'] == 4415


def test_valid_config_saved_and_standalone(app, user_headers, sched_cleanup):
    acc = _ensure_account()
    c = app.test_client()
    sid = _create_schedule(c, user_headers, acc)
    sched_cleanup.append(sid)
    cfg = {'time': {'weekdays': [1, 2], 'signTime': {'hour': 8, 'minute': 0}},
           'locationId': None, 'remarks': ['备注'], 'image': {}, 'push': {}, 'advanced': {}}
    r = c.put(f'/api/schedules/{sid}', json={'config': cfg}, headers=user_headers)
    assert r.status_code == 200
    body = r.get_json()['data']
    assert body['mode'] == 'standalone'
    s = db.session.get(Schedule, sid)
    assert s.config.get('remarks') == ['备注']
    assert not (set(s.config) - {'time', 'locationId', 'remarks', 'image', 'push', 'advanced'})
