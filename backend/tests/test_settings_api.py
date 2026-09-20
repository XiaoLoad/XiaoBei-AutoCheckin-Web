# 系统设置与系统信息接口：鉴权、往返、逐键校验、公开端点的暴露面
#
# ⚠️ system_configs 是**系统级单行数据**（不是按用户隔离的），用例写入会影响开发库与其它用例，
# 故涉及写入的用例一律挂 restore_settings：先快照全表，结束后「有行还原原值、无行则删行」。
import io
import os
from datetime import datetime

import pytest

from app.models.system_config import DEFAULTS


@pytest.fixture()
def restore_settings(app_ctx):
    """快照 system_configs 全表，用例结束后原样还原。

    设置项落库是 upsert，还原必须区分「原本就有行」与「原本没有行」——
    一律写成默认值会让后续用例读到「已落库」的状态，而 get_setting 对未落库键走的是
    注册表兜底，两条路径的 current 值可能不同（session_hours 尤其明显）。

    ⚠️updated_at 必须显式写回：该列带 onupdate，还原时的 UPDATE 会把它刷成当前时刻，
    留下「这条配置刚被改过」的假审计线索。显式赋值可压掉 onupdate。
    """
    from app.extensions import db
    from app.models.system_config import SystemConfig

    snapshot = {r.key: (r.value, r.updated_by, r.updated_at) for r in SystemConfig.query.all()}
    yield
    for row in SystemConfig.query.all():
        if row.key not in snapshot:
            db.session.delete(row)
    for key, (value, operator, updated_at) in snapshot.items():
        row = SystemConfig.query.filter_by(key=key).first()
        if row is None:
            row = SystemConfig(key=key)
            db.session.add(row)
        row.value, row.updated_by, row.updated_at = value, operator, updated_at
    db.session.commit()


def _currents(c, admin_headers):
    """把 GET /api/settings 的 items 摊成 {key: current}，便于直读断言"""
    data = c.get('/api/settings', headers=admin_headers).get_json()['data']
    return {i['key']: i['current'] for i in data['items']}, data['items']


# ── 鉴权 ──────────────────────────────────────────────────────────────
def test_settings_and_system_info_require_admin(app, user_headers):
    """未登录 401；普通用户 403（权限码 1006）；管理员端点不得被普通用户碰到"""
    c = app.test_client()
    for method, path in (('get', '/api/settings'), ('get', '/api/system/info')):
        assert getattr(c, method)(path).status_code == 401, path
        r = getattr(c, method)(path, headers=user_headers)
        assert r.status_code == 403, path
        assert r.get_json()['code'] == 1006, path
    r = c.put('/api/settings', json={'settings': {'default_quota': 100}}, headers=user_headers)
    assert r.status_code == 403 and r.get_json()['code'] == 1006


def test_public_settings_needs_no_auth_and_exposes_only_registration(app):
    """公开端点只暴露展示型开关：多暴露一个键就是信息泄漏，故用等值断言钉死键集"""
    c = app.test_client()
    r = c.get('/api/settings/public')
    assert r.status_code == 200
    data = r.get_json()['data']
    assert set(data.keys()) == {'registration_enabled'}
    assert isinstance(data['registration_enabled'], bool)


# ── 读取 ──────────────────────────────────────────────────────────────
def test_list_settings_shape_covers_registry(app, admin_headers):
    """设置项元数据必须与 DEFAULTS 注册表逐键对齐（新增配置项自动纳入，不用改前端）"""
    c = app.test_client()
    currents, items = _currents(c, admin_headers)
    assert set(currents.keys()) == set(DEFAULTS.keys())
    for it in items:
        spec = DEFAULTS[it['key']]
        for field in ('label', 'desc', 'type'):
            assert it[field] == spec[field], (it['key'], field)
        assert it['default'] is not None
        if spec['type'] == 'int':
            assert (it['min'], it['max']) == (spec['min'], spec['max'])
        else:
            assert 'min' not in it and 'max' not in it
    # session_hours 的注册表默认值是 None，须回退到 .env 的 JWT_EXPIRES_HOURS，不能给前端 null
    assert isinstance(currents['session_hours'], int)


# ── 写入往返 ───────────────────────────────────────────────────────────
def test_update_roundtrip_audit_and_trim(app, admin_headers, restore_settings):
    """往返三种类型 + 文本去空白 + 留痕操作人；响应直接回全量 items 供前端刷新表单"""
    c = app.test_client()
    r = c.put('/api/settings', headers=admin_headers, json={'settings': {
        'default_quota': 321, 'registration_enabled': False, 'amap_web_key': '  key-abc  ',
    }})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['message'] == '设置已保存'
    assert {i['key']: i['current'] for i in body['data']['items']}['default_quota'] == 321

    currents, items = _currents(c, admin_headers)
    assert currents['default_quota'] == 321
    assert currents['registration_enabled'] is False
    assert currents['amap_web_key'] == 'key-abc'   # 首尾空白已被 strip

    by_key = {i['key']: i for i in items}
    for key in ('default_quota', 'registration_enabled', 'amap_web_key'):
        assert by_key[key]['updated_by'] == 'tc_admin'
        assert by_key[key]['updated_at']          # 落库行才有的审计线索，未落库键没有


def test_update_accepts_numeric_string_for_int(app, admin_headers, restore_settings):
    """数字输入框的值到后端是字符串，须兼容；落库后经 _coerce 还原为 int"""
    c = app.test_client()
    assert c.put('/api/settings', headers=admin_headers,
                 json={'settings': {'default_quota': '300'}}).status_code == 200
    currents, _ = _currents(c, admin_headers)
    assert currents['default_quota'] == 300
    assert isinstance(currents['default_quota'], int)


# ── 逐键校验 ───────────────────────────────────────────────────────────
@pytest.mark.parametrize('payload,code', [
    ({}, 4000),                                  # 缺 settings
    ({'settings': {}}, 4000),                    # 空对象
    ({'settings': []}, 4000),                    # 类型不对
    ({'settings': {'nope': 1}}, 4001),           # 注册表外的键
    ({'settings': {'registration_enabled': 'yes'}}, 4002),   # bool 位置传字符串
    ({'settings': {'amap_web_key': 123}}, 4003),             # str 位置传数字
    ({'settings': {'default_quota': 'abc'}}, 4003),          # 不可解析
    ({'settings': {'default_quota': True}}, 4003),           # ⚠️bool 是 int 子类，不许被当数字收下
                                                             # （实际由 int(str(True)) 解析失败兜住，
                                                             #  故去掉显式 bool 守卫不会让本用例变红）
    ({'settings': {'default_quota': 0}}, 4004),              # 低于下限
    ({'settings': {'default_quota': 1000000}}, 4004),        # 高于上限
    ({'settings': {'quota_warn_ratio': 100}}, 4004),         # 比例上限为 99
    ({'settings': {'password_min_length': 3}}, 4004),        # 密码下限另有 4 位硬约束
])
def test_update_rejects_bad_payloads_without_writing(app, admin_headers, restore_settings,
                                                     payload, code):
    """逐键校验的错误码是对外契约；更要紧的是**被拒的批次一个键都不许落库**"""
    c = app.test_client()
    before, _ = _currents(c, admin_headers)
    r = c.put('/api/settings', json=payload, headers=admin_headers)
    assert r.status_code == 400, r.get_json()
    assert r.get_json()['code'] == code, r.get_json()
    after, _ = _currents(c, admin_headers)
    assert after == before


def test_update_validation_runs_before_any_write(app, admin_headers, restore_settings):
    """同一批次里混入非法键时整批拒绝：合法键也不能先落库（避免半保存）"""
    c = app.test_client()
    before, _ = _currents(c, admin_headers)
    r = c.put('/api/settings', headers=admin_headers,
              json={'settings': {'default_quota': 999, 'bogus_key': 1}})
    assert r.status_code == 400 and r.get_json()['code'] == 4001
    after, _ = _currents(c, admin_headers)
    assert after['default_quota'] == before['default_quota'] != 999


# ── 系统信息 ───────────────────────────────────────────────────────────
def test_system_info_shape_and_user_counts(app, admin_headers):
    """系统信息卡片的数据源：版本取自仓库 VERSION，用户统计须自洽"""
    from app.models.user import User

    c = app.test_client()
    r = c.get('/api/system/info', headers=admin_headers)
    assert r.status_code == 200
    data = r.get_json()['data']

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with io.open(os.path.join(root, 'VERSION'), encoding='utf-8') as f:
        assert data['version'] == f.read().strip()

    assert data['database']['status'] == 'ok'
    assert data['uptime_seconds'] >= 0
    for field in ('started_at', 'server_time'):
        datetime.strptime(data[field], '%Y-%m-%d %H:%M:%S')

    u = data['users']
    assert u['total'] == User.query.count()
    # role 白名单只有 admin/user、enabled 非空，故这两组必须刚好凑齐（漏算即口径错）
    assert u['admins'] + u['users'] == u['total']
    assert u['enabled'] + u['disabled'] == u['total']
