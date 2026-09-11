# 备注模板 {username} 渲染测试（模块 E 补充）：后端在单一出口把占位符替换为
# B 平台账号姓名（profile.name），姓名缺失时回落到登录账号标识；
# 并通过 _execute 全链路验证提交备注确实带上了对应账号的 B 平台姓名。
import uuid

from app.extensions import db
from app.models import BAccount, ConfigSet, Schedule, User
from app.services import scheduler as sch
from app.services.b_platform.base import CheckinResult


class FakeAcc:
    def __init__(self, name, account='acc_x'):
        self.account = account
        self.profile = {'name': name} if name else {}


def test_render_remark_substitutes_username():
    acc = FakeAcc('贺鑫')
    assert sch._render_remark('{username}已完成签到', acc) == '贺鑫已完成签到'


def test_render_remark_fallback_to_account():
    # 姓名缺失时回落到登录账号标识，不让字面 {username} 泄露到 B 平台
    acc = FakeAcc(None, account='13800000000')
    assert sch._render_remark('{username}签到', acc) == '13800000000签到'


def test_render_remark_no_token_unchanged():
    acc = FakeAcc('贺鑫')
    assert sch._render_remark('普通备注', acc) == '普通备注'


def test_render_remark_placeholder_passthrough():
    # 无备注占位符时原样返回，避免误伤普通备注文本
    assert sch._render_remark('—', FakeAcc('贺鑫')) == '—'


def test_select_remark_keeps_token_raw():
    # _select_remark 只负责选条，模板占位符原样保留；渲染发生在外层包装点
    resolved = {'remarks': ['{username}已完成签到']}
    assert sch._select_remark(resolved) == '{username}已完成签到'


class _OkAdapter:
    captured = None
    result = CheckinResult(ok=True, status='success')
    fence = [{'alias': '校区', 'latitude': '29.34', 'longitude': '106.53',
              'location': '某楼', 'radius': '500'}]

    def find_active_task(self, session, task_type):
        return {'task': {'id': 42, 'taskName': '查寝', 'needPhoto': False,
                         'startTime': '00:00:00', 'endTime': '23:59:59'},
                'fence': self.fence}

    def submit_checkin(self, session, task_type, task_id, location, address, remark, image=None):
        type(self).captured = remark  # 类级捕获：get_adapter() 每次返回新实例，需落到类属性
        return self.result


def test_execute_renders_username_into_submitted_remark(app_ctx, monkeypatch):
    uname = f'tc_remark_{uuid.uuid4().hex[:10]}'
    u = User(username=uname, role='user', enabled=True, quota=100, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    acc = BAccount(user_id=u.id, account=f'acc_{uname}', password_enc='x')
    acc.verify_status = 'ok'          # 跳过 verify_and_fetch，避免真实联网
    acc.set_token('tok')
    acc.set_profile({'name': '贺鑫', 'studentNo': '2021001'})
    db.session.add(acc)
    db.session.flush()

    cfg = {'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
                    'weekdays': [1, 2], 'randomDelayMax': 0, 'mode': 'normal'},
           'locationId': None, 'remarks': ['{username}已完成签到'],
           'image': {'enabled': False, 'strategy': 'recycle', 'groupId': None},
           'push': {}, 'advanced': {}, 'fence': {'intercept': True}}
    cs = ConfigSet(user_id=u.id, name='备注套')
    cs.set_config(cfg)
    db.session.add(cs)
    db.session.flush()  # 先取 cs.id，再建任务并绑定，避免 config_set_id 为 None
    s = Schedule(user_id=u.id, account_id=acc.id, task_type='dorm', mode='follow',
                 config_set_id=cs.id, enabled=True)
    db.session.add(s)
    db.session.commit()

    _OkAdapter.captured = None
    monkeypatch.setattr(sch, 'get_adapter', lambda: _OkAdapter())
    sch._execute(s)

    assert _OkAdapter.captured == '贺鑫已完成签到'

    # teardown：清理本用户关联数据，杜绝跨测试残留（注意外键顺序：先删子表再删父表）
    from app.models import SignRecord
    SignRecord.query.filter_by(user_id=u.id).delete()
    Schedule.query.filter_by(user_id=u.id).delete()
    ConfigSet.query.filter_by(user_id=u.id).delete()
    BAccount.query.filter_by(user_id=u.id).delete()
    db.session.delete(db.session.get(User, u.id))
    db.session.commit()
