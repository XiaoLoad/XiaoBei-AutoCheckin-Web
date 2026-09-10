# 提交签到调度流程层测试（模块 E）：_checkin_flow 的分支与图片认领/回滚。
# 用 FakeAdapter + 真实 DB（内存外 dev 库，用唯一用户隔离），不触真机。
import uuid

import pytest

from app.extensions import db
from app.models import BAccount, ConfigSet, PoolImage, PoolLocation, Schedule, SignRecord, User
from app.models.user import now_cst
from app.services import scheduler as sch
from app.services.b_platform.base import CheckinResult
from app.services.image_store import save_file


def _cfg(**over):
    cfg = {'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
                    'weekdays': [1, 2], 'randomDelayMax': 0, 'mode': 'normal'},
           'locationId': None, 'remarks': ['签到'],
           'image': {'enabled': False, 'strategy': 'recycle', 'groupId': None},
           'push': {}, 'advanced': {}, 'fence': {'intercept': True}}
    cfg.update(over)
    return cfg


FENCE = [{'alias': '校区', 'latitude': '29.34', 'longitude': '106.53',
          'location': '某楼', 'radius': '500'}]


class OkAdapter:
    """任务存在 + 提交成功；围栏/提交参数可捕获断言"""
    captured = None
    result = CheckinResult(ok=True, status='success')
    fence = FENCE
    need_photo = False

    def find_active_task(self, session, task_type):
        return {'task': {'id': 42, 'taskName': '07.02查寝签到', 'needPhoto': self.need_photo,
                         'startTime': '00:00:00', 'endTime': '23:59:59'},
                'fence': self.fence}

    def submit_checkin(self, session, task_type, task_id, location, address, remark, image=None):
        OkAdapter.captured = {'task_id': task_id, 'location': location, 'address': address,
                              'remark': remark, 'image': image}
        return self.result


class NoTaskAdapter:
    def find_active_task(self, session, task_type):
        return None

    def submit_checkin(self, *a, **k):
        raise AssertionError('无任务时不应提交')


class SignedTaskAdapter:
    """进行中任务存在但本人已签到（/list 中 finish 字段为 1 的行）"""

    def find_active_task(self, session, task_type):
        return {'task': None, 'fence': [],
                'finished_task': {'id': 59141, 'taskName': '大4，1.1查寝'}}

    def submit_checkin(self, *a, **k):
        raise AssertionError('已签到时不应提交')


@pytest.fixture()
def flow_env(app_ctx):
    """唯一用户 + 账号 + 独立配置的任务实例；返回 (user, acc, schedule, session)"""
    from app.utils.auth import generate_token

    uname = f'tc_flow_{uuid.uuid4().hex[:10]}'
    u = User(username=uname, role='user', enabled=True, quota=100, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()  # 先取 u.id 再建账号
    acc = BAccount(user_id=u.id, account=f'acc_{uname}', password_enc='x')
    db.session.add(acc)
    db.session.commit()

    teardown_uid = u.id

    def make_schedule(cfg):
        cs = ConfigSet(user_id=u.id, name='流程套')
        cs.set_config(cfg)
        s = Schedule(user_id=u.id, account_id=acc.id, task_type='dorm', mode='follow',
                     config_set_id=cs.id, enabled=True)
        db.session.add_all([cs, s])
        db.session.commit()
        return s

    session = {'token': 'tok', 'ua': None}
    yield {
        'uid': u.id,
        'acc': acc,
        'session': session,
        'make_schedule': make_schedule,
    }
    # teardown：清理本用户关联数据，杜绝跨测试残留
    SignRecord.query.filter_by(user_id=teardown_uid).delete()
    Schedule.query.filter_by(user_id=teardown_uid).delete()
    ConfigSet.query.filter_by(user_id=teardown_uid).delete()
    PoolImage.query.filter_by(user_id=teardown_uid).delete()
    PoolLocation.query.filter_by(user_id=teardown_uid).delete()
    BAccount.query.filter_by(user_id=teardown_uid).delete()
    db.session.delete(db.session.get(User, teardown_uid))
    db.session.commit()


def _make_location(uid, lat=29.34, lng=106.53):
    loc = PoolLocation(user_id=uid, name='寝室', address='某楼', lat=lat, lng=lng,
                       offset_m=10, enabled=True)
    db.session.add(loc)
    db.session.commit()
    return loc


def _make_image(uid, content=b'jpeg-a'):
    fname = save_file(uid, content, '.jpg')
    img = PoolImage(user_id=uid, orig_name='a.jpg', filename=fname,
                    size=len(content), mime='image/jpeg', status='active')
    db.session.add(img)
    db.session.commit()
    return img


def test_no_active_task_skips(flow_env, monkeypatch):
    env = flow_env
    s = env['make_schedule'](_cfg())
    monkeypatch.setattr(sch, 'get_adapter', lambda: NoTaskAdapter())
    outcome, reason, _ = sch._checkin_flow(s, env['acc'], env['session'], _cfg(), '签到')
    assert outcome == 'skip'
    assert '无进行中' in reason


def test_already_signed_skips_with_distinct_reason(flow_env, monkeypatch):
    """已签到与「本来就没任务」必须落成两种文案——同报「无进行中任务」会把
    已签误判成漏签（该歧义来自真机实测），且两种情况都不应发起提交。"""
    env = flow_env
    s = env['make_schedule'](_cfg())
    monkeypatch.setattr(sch, 'get_adapter', lambda: SignedTaskAdapter())
    outcome, reason, _ = sch._checkin_flow(s, env['acc'], env['session'], _cfg(), '签到')
    assert outcome == 'skip'
    assert '已完成签到' in reason and '大4，1.1查寝' in reason


def test_fence_intercept_blocks_when_out_of_radius(flow_env, monkeypatch):
    env = flow_env
    loc = _make_location(env['uid'], lat=30.34, lng=106.53)  # 距围栏中心约 111km
    cfg = _cfg(locationId=loc.id, fence={'intercept': True})
    s = env['make_schedule'](cfg)
    adapter = OkAdapter()
    monkeypatch.setattr(sch, 'get_adapter', lambda: adapter)

    outcome, reason, _ = sch._checkin_flow(s, env['acc'], env['session'], cfg, '签到')
    assert outcome == 'fail'
    assert '围栏拦截' in reason and '超出围栏半径' in reason
    assert adapter.captured is None  # 被拦截则不发起提交


def test_fence_intercept_off_submits_anyway(flow_env, monkeypatch):
    env = flow_env
    loc = _make_location(env['uid'], lat=30.34, lng=106.53)
    cfg = _cfg(locationId=loc.id, fence={'intercept': False})
    s = env['make_schedule'](cfg)
    adapter = OkAdapter()
    monkeypatch.setattr(sch, 'get_adapter', lambda: adapter)

    outcome, reason, _ = sch._checkin_flow(s, env['acc'], env['session'], cfg, '签到')
    assert outcome == 'success'
    assert adapter.captured['location'].startswith('106.5')  # 经度在前
    assert adapter.captured['remark'] == '签到'


def test_in_radius_submits_and_location_format(flow_env, monkeypatch):
    env = flow_env
    loc = _make_location(env['uid'], lat=29.3401, lng=106.5301)  # 围栏中心附近
    cfg = _cfg(locationId=loc.id)
    s = env['make_schedule'](cfg)
    adapter = OkAdapter()
    monkeypatch.setattr(sch, 'get_adapter', lambda: adapter)

    outcome, _, _ = sch._checkin_flow(s, env['acc'], env['session'], cfg, '签到')
    assert outcome == 'success'
    lng, lat = adapter.captured['location'].split(':')  # location 为 "经度:纬度"
    assert abs(float(lat) - 29.3401) < 0.001
    assert abs(float(lng) - 106.5301) < 0.001


def test_need_photo_without_image_fails(flow_env, monkeypatch):
    env = flow_env
    s = env['make_schedule'](_cfg())
    adapter = OkAdapter()
    adapter.need_photo = True
    monkeypatch.setattr(sch, 'get_adapter', lambda: adapter)

    outcome, reason, _ = sch._checkin_flow(s, env['acc'], env['session'], _cfg(), '签到')
    assert outcome == 'fail'
    assert '需要上传签到图片' in reason


def test_image_claimed_on_success_trash(flow_env, monkeypatch):
    env = flow_env
    img = _make_image(env['uid'], b'jpeg-ok')
    cfg = _cfg(image={'enabled': True, 'strategy': 'trash', 'groupId': None})
    s = env['make_schedule'](cfg)
    adapter = OkAdapter()
    monkeypatch.setattr(sch, 'get_adapter', lambda: adapter)

    outcome, _, extra = sch._checkin_flow(s, env['acc'], env['session'], cfg, '签到')
    assert outcome == 'success'
    assert adapter.captured['image']['bytes'] == b'jpeg-ok'
    assert adapter.captured['image']['filename'].endswith('.jpeg')
    row = db.session.get(PoolImage, img.id)
    assert row.status == 'trash'          # trash 策略：成功后进回收站
    assert extra['image_id'] == img.id


def test_image_claim_rolled_back_on_submit_fail(flow_env, monkeypatch):
    env = flow_env
    img = _make_image(env['uid'], b'jpeg-b')
    cfg = _cfg(image={'enabled': True, 'strategy': 'recycle', 'groupId': None})
    s = env['make_schedule'](cfg)
    adapter = OkAdapter()
    adapter.result = CheckinResult(ok=False, status='fail', fail_reason='平台拒绝')
    monkeypatch.setattr(sch, 'get_adapter', lambda: adapter)

    outcome, reason, _ = sch._checkin_flow(s, env['acc'], env['session'], cfg, '签到')
    assert outcome == 'fail'
    row = db.session.get(PoolImage, img.id)
    assert row.status == 'active'         # recycle 策略失败回滚：图片恢复可用


def test_no_location_falls_back_to_fence_center(flow_env, monkeypatch):
    env = flow_env
    cfg = _cfg(locationId=None)
    s = env['make_schedule'](cfg)
    adapter = OkAdapter()
    monkeypatch.setattr(sch, 'get_adapter', lambda: adapter)

    outcome, _, _ = sch._checkin_flow(s, env['acc'], env['session'], cfg, '签到')
    assert outcome == 'success'
    lng, lat = adapter.captured['location'].split(':')  # location 为 "经度:纬度"
    assert abs(float(lat) - 29.34) < 0.001       # 围栏中心 ± 10m
    assert abs(float(lng) - 106.53) < 0.001
