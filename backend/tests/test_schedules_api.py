# backend/tests/test_schedules_api.py
# 模块 B：schedules 蓝图 —— 列表 / 显式创建 / 删除 / 开启校验（4401/4402）
# 定时任务不再随账号自动生成（方案 2：用户显式创建），所有用例均通过 POST /api/schedules 建立实例。
# 写与读均走 HTTP 请求事务，规避直写会话与请求会话的连接可见性差异。
import os

os.environ['USE_STUB_BPLATFORM'] = '1'

import uuid


def _uid(c, headers):
    return c.get('/api/auth/me', headers=headers).get_json()['data']['user_id']


def _create_account(c, headers):
    """通过真实接口创建账号（桩适配器校验通过），返回账号 id"""
    name = f'tc_{uuid.uuid4().hex[:12]}'
    r = c.post('/api/accounts',
               json={'account': name, 'password': 'x1', 'type': 'dorm'},
               headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()['data']['id']


def _create_schedule(c, headers, acc_id, task_type='dorm'):
    """显式创建定时任务（账号 × 类型），返回任务 id；已存在则复用已有"""
    r = c.post('/api/schedules',
               json={'accountId': acc_id, 'taskType': task_type},
               headers=headers)
    assert r.status_code in (200, 201), r.get_json()
    return r.get_json()['data']['id']


def _delete_account(c, headers, acc_id):
    c.delete(f'/api/accounts/{acc_id}', headers=headers)


def _default_set_id(c, headers):
    items = c.get('/api/config-sets', headers=headers).get_json()['data']['items']
    default = next((it for it in items if it['isDefault']), None)
    return default['id'] if default else None


def test_list_returns_user_schedules(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        _create_schedule(c, user_headers, acc_id, 'dorm')
        _create_schedule(c, user_headers, acc_id, 'activity')
        r = c.get('/api/schedules', headers=user_headers)
        assert r.status_code == 200
        items = r.get_json()['data']['items']
        assert len(items) >= 2
        assert all(it['accountId'] == acc_id for it in items)
        assert all('nextRunAt' in it and 'accountName' in it for it in items)
        # 未启用任务 nextRunAt 应为空
        assert all(it['nextRunAt'] == '' for it in items if not it['enabled'])
    finally:
        _delete_account(c, user_headers, acc_id)


def test_create_schedule_explicit(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        sid = _create_schedule(c, user_headers, acc_id, 'dorm')
        items = c.get('/api/schedules', headers=user_headers).get_json()['data']['items']
        it = next(x for x in items if x['id'] == sid)
        assert it['accountId'] == acc_id
        assert it['taskType'] == 'dorm'
        assert it['mode'] == 'follow'
        assert it['enabled'] is False
        assert it['configSetId'] is None
    finally:
        _delete_account(c, user_headers, acc_id)


def test_create_duplicate_idempotent(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        sid1 = _create_schedule(c, user_headers, acc_id, 'dorm')
        r2 = c.post('/api/schedules',
                    json={'accountId': acc_id, 'taskType': 'dorm'},
                    headers=user_headers)
        assert r2.status_code == 200
        assert '已存在' in r2.get_json()['message']
        assert r2.get_json()['data']['id'] == sid1
        items = c.get('/api/schedules', headers=user_headers).get_json()['data']['items']
        assert sum(1 for x in items if x['accountId'] == acc_id and x['taskType'] == 'dorm') == 1
    finally:
        _delete_account(c, user_headers, acc_id)


def test_create_invalid_task_type(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        r = c.post('/api/schedules',
                   json={'accountId': acc_id, 'taskType': 'weekend'},
                   headers=user_headers)
        assert r.status_code == 400
        assert r.get_json()['code'] == 4411
    finally:
        _delete_account(c, user_headers, acc_id)


def test_create_nonint_account_rejected(app, user_headers):
    c = app.test_client()
    r = c.post('/api/schedules',
               json={'accountId': 'abc', 'taskType': 'dorm'},
               headers=user_headers)
    assert r.status_code == 400
    assert r.get_json()['code'] == 4410


def test_create_disabled_account_rejected(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        c.put(f'/api/accounts/{acc_id}', json={'enabled': False}, headers=user_headers)
        r = c.post('/api/schedules',
                   json={'accountId': acc_id, 'taskType': 'dorm'},
                   headers=user_headers)
        assert r.status_code == 400
        assert r.get_json()['code'] == 4407
    finally:
        _delete_account(c, user_headers, acc_id)


def test_delete_schedule(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        sid = _create_schedule(c, user_headers, acc_id, 'dorm')
        rd = c.delete(f'/api/schedules/{sid}', headers=user_headers)
        assert rd.status_code == 200
        items = c.get('/api/schedules', headers=user_headers).get_json()['data']['items']
        assert all(x['id'] != sid for x in items)
    finally:
        _delete_account(c, user_headers, acc_id)


def test_delete_other_user_forbidden(app, user_headers, admin_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        sid = _create_schedule(c, user_headers, acc_id, 'dorm')
        # 另一用户（admin）删除该任务：按 user_id 隔离，查无 → 4040
        rd = c.delete(f'/api/schedules/{sid}', headers=admin_headers)
        assert rd.status_code == 404
        assert rd.get_json()['code'] == 4040
        # 原用户仍能看到该任务
        items = c.get('/api/schedules', headers=user_headers).get_json()['data']['items']
        assert any(x['id'] == sid for x in items)
    finally:
        _delete_account(c, user_headers, acc_id)


def test_enable_follow_without_config_rejected(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        sid = _create_schedule(c, user_headers, acc_id, 'dorm')
        r = c.put(f'/api/schedules/{sid}', json={'enabled': True, 'mode': 'follow'}, headers=user_headers)
        assert r.status_code == 400
        assert r.get_json()['code'] == 4401
    finally:
        _delete_account(c, user_headers, acc_id)


def test_bind_nonexistent_config_set_rejected(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        sid = _create_schedule(c, user_headers, acc_id, 'dorm')
        r = c.put(f'/api/schedules/{sid}', json={'configSetId': 999999}, headers=user_headers)
        assert r.status_code == 400
        assert r.get_json()['code'] == 4400
    finally:
        _delete_account(c, user_headers, acc_id)


def test_invalid_custom_rejected(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        sid = _create_schedule(c, user_headers, acc_id, 'dorm')
        # 自定义参数缺 weekdays → 结构校验拦截（4405），不会到达开启校验
        r = c.put(f'/api/schedules/{sid}',
                  json={'enabled': True, 'mode': 'custom', 'custom': {'hour': 8, 'minute': 0}},
                  headers=user_headers)
        assert r.status_code == 400
        assert r.get_json()['code'] == 4405
    finally:
        _delete_account(c, user_headers, acc_id)


def test_enable_custom_valid_sets_next_run(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        sid = _create_schedule(c, user_headers, acc_id, 'dorm')
        r = c.put(f'/api/schedules/{sid}',
                  json={'enabled': True, 'mode': 'custom',
                        'custom': {'hour': 8, 'minute': 0, 'weekdays': [1, 2, 3, 4, 5]}},
                  headers=user_headers)
        assert r.status_code == 200
        body = r.get_json()['data']
        assert body['enabled'] is True
        assert body['nextRunAt']  # 下次执行时间已被计算并缓存
    finally:
        _delete_account(c, user_headers, acc_id)


def test_enable_follow_with_default_set(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        default_id = _default_set_id(c, user_headers)
        assert default_id is not None
        sid = _create_schedule(c, user_headers, acc_id, 'dorm')
        r = c.put(f'/api/schedules/{sid}',
                  json={'enabled': True, 'mode': 'follow', 'configSetId': default_id},
                  headers=user_headers)
        assert r.status_code == 200
        body = r.get_json()['data']
        assert body['enabled'] is True
        assert body['configSetId'] == default_id
    finally:
        _delete_account(c, user_headers, acc_id)


def test_apply_config_set_sets_follow_mode(app, user_headers):
    # 模块 C：仅传 configSetId（不传 mode）即视为"应用配置套"，后端自动置 mode=follow
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        default_id = _default_set_id(c, user_headers)
        assert default_id is not None
        sid = _create_schedule(c, user_headers, acc_id, 'dorm')
        r = c.put(f'/api/schedules/{sid}', json={'configSetId': default_id}, headers=user_headers)
        assert r.status_code == 200
        body = r.get_json()['data']
        assert body['configSetId'] == default_id
        assert body['mode'] == 'follow'
    finally:
        _delete_account(c, user_headers, acc_id)


def test_disable_clears_next_run(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        sid = _create_schedule(c, user_headers, acc_id, 'dorm')
        c.put(f'/api/schedules/{sid}',
              json={'enabled': True, 'mode': 'custom',
                    'custom': {'hour': 8, 'minute': 0, 'weekdays': [1]}},
              headers=user_headers)
        r2 = c.put(f'/api/schedules/{sid}', json={'enabled': False}, headers=user_headers)
        assert r2.status_code == 200
        assert r2.get_json()['data']['nextRunAt'] == ''
    finally:
        _delete_account(c, user_headers, acc_id)
