# UA 变体派生回归：生成器确定性、维度正确、数量上限、去重；端点权限与入库行为。
import uuid

import pytest

from app.extensions import db
from app.models import PoolUa, User
from app.services.ua_variants import derive_variants

ANDROID_UA = ('Mozilla/5.0 (Linux; Android 14; 23127PN0CC Build/UKQ1.230804.001; wv) '
              'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.6099.43 '
              'Mobile Safari/537.36 uni-app (Immersed/24.0)')
IOS_UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) '
          'AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 uni-app (Immersed/24.0)')
DESKTOP_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'


# ---------- 生成器（纯逻辑） ----------

def test_android_variants_dimensions():
    """Android 模板：系统版本 / Build / Chrome 版本三维均被替换，机型名保留"""
    out = derive_variants(ANDROID_UA, count=12)
    assert out, 'Android 模板应能派生'
    assert all('23127PN0CC' in v for v in out), '机型型号不变'
    assert all(v != ANDROID_UA for v in out)
    # 至少出现两个不同的 Android 版本与两个不同的 Chrome 主版本（维度真的在动）
    import re
    vers = {re.search(r'Android (\d+);', v).group(1) for v in out}
    chromes = {re.search(r'Chrome/(\d+)', v).group(1) for v in out}
    assert len(vers) > 1 and len(chromes) > 1


def test_ios_variants_change_os_only():
    """iOS 模板：系统版本替换、机型段与 AppleWebKit 版本保留"""
    out = derive_variants(IOS_UA, count=12)
    assert out, 'iOS 模板应能派生'
    assert all('iPhone' in v for v in out)
    assert all('AppleWebKit/605.1.15' in v for v in out)
    assert all(v != IOS_UA for v in out)
    import re
    vers = {re.search(r'iPhone OS (\d+_\d+)', v).group(1) for v in out}
    assert len(vers) > 1
    assert '18_2' not in vers, '原版本不应重复出现'


def test_deterministic_generation():
    """同模板多次派生结果完全一致（确定性生成，便于排查与测试）"""
    assert derive_variants(ANDROID_UA, count=6) == derive_variants(ANDROID_UA, count=6)
    assert derive_variants(IOS_UA, count=6) == derive_variants(IOS_UA, count=6)


def test_count_clamp_and_unrecognized():
    """数量钳制到 1~12；无法识别的 UA 形态返回空列表"""
    assert len(derive_variants(ANDROID_UA, count=0)) == 1
    assert len(derive_variants(ANDROID_UA, count=99)) <= 12
    assert derive_variants(DESKTOP_UA) == []
    assert derive_variants('') == []
    assert derive_variants(None) == []


def test_no_duplicate_within_variants():
    """变体之间不重复（不循环拼凑）"""
    out = derive_variants(ANDROID_UA, count=12)
    assert len(out) == len(set(out))


# ---------- 端点（管理员鉴权 + 入库去重） ----------

@pytest.fixture()
def ua_admin_env(app_ctx):
    uname = f'tc_uad_{uuid.uuid4().hex[:8]}'
    u = User(username=uname, role='admin', enabled=True, quota=10, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    tpl = PoolUa(user_id=u.id, is_system=True, content=ANDROID_UA, remark='小米14', enabled=True)
    db.session.add(tpl)
    db.session.commit()
    from app.utils.auth import generate_token
    yield {'uid': u.id, 'tpl': tpl, 'headers': {'Authorization': f'Bearer {generate_token(u)}'}}
    db.session.rollback()


def test_derive_endpoint_creates_enabled_variants(app_ctx, ua_admin_env):
    """端点：管理员派生成功，变体入库且启用、remark 带机型名"""
    client = app_ctx.test_client()
    tpl_id = ua_admin_env['tpl'].id
    resp = client.post(f'/api/pools/uas/{tpl_id}/derive',
                       json={'count': 5}, headers=ua_admin_env['headers'])
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert len(data['added']) == 5
    rows = [db.session.get(PoolUa, r['id']) for r in data['added']]
    assert all(r.enabled for r in rows)
    assert all('小米14' in r.remark for r in rows)
    assert all(r.content != ANDROID_UA for r in rows)


def test_derive_endpoint_dedup_against_pool(app_ctx, ua_admin_env):
    """重复派生：与池内已有 content 去重——第二次派生不再新增任何行，全部计入 skipped"""
    client = app_ctx.test_client()
    tpl_id = ua_admin_env['tpl'].id
    h = ua_admin_env['headers']
    r1 = client.post(f'/api/pools/uas/{tpl_id}/derive', json={'count': 5}, headers=h)
    assert r1.status_code == 200
    added1 = r1.get_json()['data']['added']
    # 池内可能出现其他用例写入的同 content 变体（共享 dev 库），首个测试前先清场
    if not added1:
        assert r1.get_json()['data']['skipped'] == 5
        return
    r2 = client.post(f'/api/pools/uas/{tpl_id}/derive', json={'count': 5}, headers=h)
    assert r2.status_code == 200
    data = r2.get_json()['data']
    assert data['added'] == [], '同一模板二次派生不应新增（生成确定性 + 去重）'
    assert data['skipped'] == 5


def test_derive_endpoint_rejects_non_admin(app_ctx, ua_admin_env):
    """普通用户 403（admin_required）"""
    client = app_ctx.test_client()
    uname = f'tc_uau_{uuid.uuid4().hex[:8]}'
    u = User(username=uname, role='user', enabled=True, quota=10, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    from app.utils.auth import generate_token
    resp = client.post(f"/api/pools/uas/{ua_admin_env['tpl'].id}/derive",
                       json={'count': 3},
                       headers={'Authorization': f'Bearer {generate_token(u)}'})
    assert resp.status_code == 403


def test_derive_endpoint_unrecognized_ua_400(app_ctx, ua_admin_env):
    """无法识别的 UA 形态返回 400 业务错误"""
    client = app_ctx.test_client()
    row = PoolUa(user_id=ua_admin_env['uid'], is_system=True,
                 content=DESKTOP_UA, remark='桌面', enabled=True)
    db.session.add(row)
    db.session.commit()
    resp = client.post(f'/api/pools/uas/{row.id}/derive',
                       json={'count': 3}, headers=ua_admin_env['headers'])
    assert resp.status_code == 400
