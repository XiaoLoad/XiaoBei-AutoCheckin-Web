# 资源池接口测试：UA 池（admin 管理 + 引用保护）+ 凭证池（脱敏回显 / 占位更新）
# 另含 Task 6 评审补充的位置池越权/引用/排序用例
from app.extensions import db
from app.models import ConfigSet, PoolCredential, User


def _ua(name='小米 14'):
    return {'content': 'Mozilla/5.0 (Linux; Android 14) Chrome/120 Mobile', 'remark': name}


def _loc_body(name='我的寝室', scope=None):
    b = {'name': name, 'address': '某大学 6 栋', 'lat': 30.1255, 'lng': 120.4589,
         'offset': 20, 'enabled': True}
    if scope:
        b['scope'] = scope
    return b


def test_ua_admin_only_and_crud(app, user_headers, admin_headers):
    c = app.test_client()
    assert c.post('/api/pools/uas', json=_ua(), headers=user_headers).status_code == 403
    r = c.post('/api/pools/uas', json=_ua(), headers=admin_headers)
    assert r.status_code == 201
    uid = r.get_json()['data']['id']
    assert r.get_json()['data']['isSystem'] is True
    # 普通用户聚合可见 UA（读不拦）
    data = c.get('/api/pools', headers=user_headers).get_json()['data']
    assert any(u['id'] == uid for u in data['uas'])
    assert c.put(f'/api/pools/uas/{uid}', json={'remark': '华为 Mate60'},
                 headers=admin_headers).get_json()['data']['remark'] == '华为 Mate60'
    assert c.delete(f'/api/pools/uas/{uid}', headers=admin_headers).status_code == 200


def test_ua_bulk_delete_blocked_by_reference(app, user_headers, admin_headers):
    c = app.test_client()
    uid = c.post('/api/pools/uas', json=_ua('被引用'), headers=admin_headers).get_json()['data']['id']
    # 造一个引用它的配置套（owner 用真实用户 id，防 FK 违例）
    owner_id = User.query.first().id
    cs = ConfigSet(user_id=owner_id, name='引用套', is_default=False)
    cs.set_config({'advanced': {'uaTemplateId': uid}, 'time': {'weekdays': [1]},
                   'remarks': [], 'image': {}, 'push': {}})
    db.session.add(cs)
    db.session.commit()
    r = c.post('/api/pools/uas/bulk-delete', json={'ids': [uid]}, headers=admin_headers)
    assert r.status_code == 409 and r.get_json()['code'] == 4311
    db.session.delete(cs)
    db.session.commit()
    assert c.post('/api/pools/uas/bulk-delete', json={'ids': [uid]},
                  headers=admin_headers).status_code == 200


def test_credential_masked_roundtrip(app, user_headers):
    c = app.test_client()
    body = {'channel': 'email', 'name': '通知邮箱',
            'fields': {'emailSmtp': 'smtp.qq.com', 'emailFrom': 'a@x.com',
                       'emailPass': 'SECRET123', 'emailTo': 'b@x.com'}}
    cid = c.post('/api/pools/credentials', json=body, headers=user_headers).get_json()['data']['id']
    got = c.get('/api/pools', headers=user_headers).get_json()['data']['credentials'][0]
    assert got['fields']['emailPass'] == '••••T123'      # 尾4位脱敏
    assert got['fields']['emailSmtp'] == 'smtp.qq.com'   # 非密文原样
    # 更新：密码传占位（保持旧值），SMTP 改新值 → 合并后仍合法
    upd = {'fields': {'emailSmtp': 'smtp.163.com', 'emailFrom': 'a@x.com',
                      'emailPass': '••••E123', 'emailTo': 'b@x.com'}, 'name': '新名字'}
    r = c.put(f'/api/pools/credentials/{cid}', json=upd, headers=user_headers)
    assert r.status_code == 200 and r.get_json()['data']['name'] == '新名字'
    row = PoolCredential.query.get(cid)
    from app.services.crypto import decrypt
    import json as _json
    merged = _json.loads(decrypt(row.secret_enc))
    assert merged['emailPass'] == 'SECRET123' and merged['emailSmtp'] == 'smtp.163.com'
    assert c.delete(f'/api/pools/credentials/{cid}', headers=user_headers).status_code == 200


# ---------- Task 6 评审补充覆盖：位置池越权 / 引用删除 / 聚合排序 ----------

def test_location_foreign_write_returns_404(app, user_headers, admin_headers):
    """他人私有位置对外不可见：PUT/DELETE 均 404（管理员也不例外）"""
    c = app.test_client()
    lid = c.post('/api/pools/locations', json=_loc_body('甲的私有'),
                 headers=user_headers).get_json()['data']['id']
    assert c.put(f'/api/pools/locations/{lid}', json=_loc_body('偷改'),
                 headers=admin_headers).status_code == 404
    assert c.delete(f'/api/pools/locations/{lid}', headers=admin_headers).status_code == 404
    c.delete(f'/api/pools/locations/{lid}', headers=user_headers)


def test_location_system_guard_on_put(app, user_headers, admin_headers):
    """普通用户 PUT 系统位置 → 403 / code 4302"""
    c = app.test_client()
    sys_lid = c.post('/api/pools/locations', json=_loc_body('系统位', scope='system'),
                     headers=admin_headers).get_json()['data']['id']
    resp = c.put(f'/api/pools/locations/{sys_lid}', json=_loc_body('乱改'), headers=user_headers)
    assert resp.status_code == 403 and resp.get_json()['code'] == 4302
    c.delete(f'/api/pools/locations/{sys_lid}', headers=admin_headers)


def test_location_delete_blocked_by_config_reference(app, user_headers):
    """删除被 ConfigSet.location_id 引用的位置 → 409 / code 4303"""
    c = app.test_client()
    lid = c.post('/api/pools/locations', json=_loc_body('被引用位置'),
                 headers=user_headers).get_json()['data']['id']
    cs = ConfigSet(user_id=User.query.filter_by(username='tc_user').first().id,
                   name='引用位置的套', is_default=False, location_id=lid)
    cs.set_config({'advanced': {'uaTemplateId': None}, 'time': {'weekdays': [1]},
                   'remarks': [], 'image': {}, 'push': {}})
    db.session.add(cs)
    db.session.commit()
    resp = c.delete(f'/api/pools/locations/{lid}', headers=user_headers)
    assert resp.status_code == 409 and resp.get_json()['code'] == 4303
    db.session.delete(cs)
    db.session.commit()
    assert c.delete(f'/api/pools/locations/{lid}', headers=user_headers).status_code == 200


def test_aggregate_locations_system_before_private(app, user_headers, admin_headers):
    """聚合 locations 排序：系统行整体排在私有行之前"""
    c = app.test_client()
    sys_ids = [c.post('/api/pools/locations', json=_loc_body(f'系统{i}', scope='system'),
                      headers=admin_headers).get_json()['data']['id'] for i in range(2)]
    own_ids = [c.post('/api/pools/locations', json=_loc_body(f'私有{i}'),
                      headers=user_headers).get_json()['data']['id'] for i in range(2)]
    locs = c.get('/api/pools', headers=user_headers).get_json()['data']['locations']
    ids = [l['id'] for l in locs]
    assert set(sys_ids) <= set(ids) and set(own_ids) <= set(ids)
    seen_private = False
    for l in locs:
        if l['isSystem']:
            assert not seen_private, f'系统行出现在私有行之后: {ids}'
        else:
            seen_private = True
    # 清理
    for i in own_ids:
        c.delete(f'/api/pools/locations/{i}', headers=user_headers)
    for i in sys_ids:
        c.delete(f'/api/pools/locations/{i}', headers=admin_headers)
