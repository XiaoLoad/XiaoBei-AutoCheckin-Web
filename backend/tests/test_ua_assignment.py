# UA 开关式双模式回归：机型池分配（按账号确定性散开）/ 自定义 UA 全员统一 /
# 旧数据（uaTemplateId 无 uaPoolEnabled）语义保持关闭。
import uuid

import pytest

from app.extensions import db
from app.models import BAccount, PoolUa, User
from app.services import scheduler as sch


@pytest.fixture()
def ua_env(app_ctx):
    uname = f'tc_ua_{uuid.uuid4().hex[:10]}'
    u = User(username=uname, role='user', enabled=True, quota=10, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    accs = [BAccount(user_id=u.id, account=f'ua_{uname}_{i}', password_enc='x')
            for i in range(6)]
    db.session.add_all(accs)
    db.session.commit()
    yield {'uid': u.id, 'accs': accs, 'user': u}
    # teardown：conftest 会话级按 tc_ 前缀级联清理，这里仅回滚未提交改动
    db.session.rollback()


def _mk_templates(uid, n=4):
    rows = [PoolUa(user_id=uid, content=f'UA-TEMPLATE-{i}', remark=f'机型{i}')
            for i in range(n)]
    db.session.add_all(rows)
    db.session.commit()
    return rows


def _pool_resolved():
    return {'advanced': {'uaPoolEnabled': True, 'customUa': ''}}


def test_pool_mode_spreads_accounts(ua_env):
    """机型池开启：同配置套的多账号分配到多条模板，而非全员同一条"""
    tpls = _mk_templates(ua_env['uid'])
    got = {sch._resolve_ua(_pool_resolved(), a.id, ua_env['uid']) for a in ua_env['accs']}
    assert len(got) > 1, f'6 个账号 4 条模板应散开，实际全部相同: {got}'
    assert got <= {t.content for t in tpls}


def test_pool_mode_same_account_stable(ua_env):
    """机型池开启：同账号多次解析恒定（设备身份不漂移）"""
    _mk_templates(ua_env['uid'])
    acc = ua_env['accs'][0]
    first = sch._resolve_ua(_pool_resolved(), acc.id, ua_env['uid'])
    assert first
    assert all(sch._resolve_ua(_pool_resolved(), acc.id, ua_env['uid']) == first
               for _ in range(3))


def test_custom_mode_uses_custom_ua_for_all(ua_env):
    """自定义模式：customUa 非空全员统一，即使机型池有模板也不参与"""
    _mk_templates(ua_env['uid'])
    resolved = {'advanced': {'uaPoolEnabled': False, 'customUa': 'MY-CUSTOM-UA'}}
    for acc in ua_env['accs']:
        assert sch._resolve_ua(resolved, acc.id, ua_env['uid']) == 'MY-CUSTOM-UA'


def test_custom_mode_empty_falls_back_to_none(ua_env):
    """自定义模式：customUa 留空回退 None（适配器默认 UA），机型池模板不参与"""
    _mk_templates(ua_env['uid'])
    resolved = {'advanced': {'uaPoolEnabled': False, 'customUa': ''}}
    assert sch._resolve_ua(resolved, ua_env['accs'][0].id, ua_env['uid']) is None


def test_legacy_template_id_without_switch_stays_off(ua_env):
    """旧数据兼容：uaTemplateId 存在但 uaPoolEnabled 未开 → 不自动改变行为（回退默认 UA）"""
    tpls = _mk_templates(ua_env['uid'])
    resolved = {'advanced': {'uaTemplateId': tpls[0].id, 'customUa': ''}}
    assert sch._resolve_ua(resolved, ua_env['accs'][0].id, ua_env['uid']) is None


def test_empty_pool_returns_none(ua_env):
    """机型池开启但无启用模板 → 回退 None（适配器默认 UA），不抛异常"""
    assert sch._resolve_ua(_pool_resolved(), ua_env['accs'][0].id, ua_env['uid']) is None


def test_disabled_templates_excluded(ua_env):
    """禁用模板不参与分配：3 启用 + 1 禁用，命中结果只落启用集合"""
    tpls = _mk_templates(ua_env['uid'], n=3)
    db.session.add(PoolUa(user_id=ua_env['uid'], content='UA-DISABLED', enabled=False))
    db.session.commit()
    got = {sch._resolve_ua(_pool_resolved(), a.id, ua_env['uid']) for a in ua_env['accs']}
    assert 'UA-DISABLED' not in got
    assert got <= {t.content for t in tpls}


def test_account_id_none_takes_first(ua_env):
    """account_id 为 None（预览场景）取池中第一条"""
    tpls = _mk_templates(ua_env['uid'])
    assert sch._resolve_ua(_pool_resolved(), None, ua_env['uid']) == tpls[0].content
