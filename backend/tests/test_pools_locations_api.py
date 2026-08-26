# 资源池接口测试：位置池 CRUD + 四池聚合可见性（is_system 或本人私有）
from app.extensions import db
from app.models import PoolLocation


def _loc_body(name='我的寝室', scope=None):
    b = {'name': name, 'address': '某大学 6 栋', 'lat': 30.1255, 'lng': 120.4589,
         'offset': 20, 'enabled': True}
    if scope:
        b['scope'] = scope
    return b


def test_location_crud_and_visibility(app, user_headers, admin_headers):
    c = app.test_client()
    # 用户建私有位置
    r = c.post('/api/pools/locations', json=_loc_body(), headers=user_headers)
    assert r.status_code == 201
    lid = r.get_json()['data']['id']
    assert r.get_json()['data']['isSystem'] is False
    # 用户不能建系统位置
    assert c.post('/api/pools/locations', json=_loc_body(scope='system'),
                  headers=user_headers).status_code == 403
    # 管理员建系统位置
    r = c.post('/api/pools/locations', json=_loc_body('图书馆', scope='system'),
               headers=admin_headers)
    assert r.status_code == 201 and r.get_json()['data']['isSystem'] is True
    sys_lid = r.get_json()['data']['id']
    # 聚合：用户可见 自己的 + 系统的
    data = c.get('/api/pools', headers=user_headers).get_json()['data']
    ids = {l['id'] for l in data['locations']}
    assert {lid, sys_lid} <= ids and len(data['credentials']) == 0
    # 越权改删系统位置：普通用户 403
    assert c.delete(f'/api/pools/locations/{sys_lid}', headers=user_headers).status_code == 403
    # 更新自己的
    assert c.put(f'/api/pools/locations/{lid}',
                 json=_loc_body('我的寝室2'), headers=user_headers).get_json()['data']['name'] == '我的寝室2'
    # 清理
    assert c.delete(f'/api/pools/locations/{lid}', headers=user_headers).status_code == 200
    assert c.delete(f'/api/pools/locations/{sys_lid}', headers=admin_headers).status_code == 200
