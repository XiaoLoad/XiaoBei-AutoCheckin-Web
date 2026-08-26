# backend/tests/test_schedules_api.py
# 模块 B：schedules 蓝图 —— 列表 / 更新 / 开启校验（4401/4402）/ 引用保护联动
# 用桩适配器使 POST /api/accounts 无需真实 B 平台即可创建账号与自动任务，
# 写与读均走 HTTP 请求事务，规避直写会话与请求会话的连接可见性差异。
import os

os.environ['USE_STUB_BPLATFORM'] = '1'

import uuid


def _uid(c, headers):
    return c.get('/api/auth/me', headers=headers).get_json()['data']['user_id']


def _create_account(c, headers):
    """通过真实接口创建账号（桩适配器校验通过），自动生成 dorm/activity 两条任务，返回账号 id"""
    name = f'tc_{uuid.uuid4().hex[:12]}'
    r = c.post('/api/accounts',
               json={'account': name, 'password': 'x1', 'type': 'dorm'},
               headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()['data']['id']


def _delete_account(c, headers, acc_id):
    c.delete(f'/api/accounts/{acc_id}', headers=headers)


def _default_set_id(c, headers):
    items = c.get('/api/config-sets', headers=headers).get_json()['data']['items']
    default = next((it for it in items if it['isDefault']), None)
    return default['id'] if default else None


def _dorm_id(c, headers, acc_id):
    items = c.get('/api/schedules', headers=headers).get_json()['data']['items']
    return next(it['id'] for it in items if it['accountId'] == acc_id and it['taskType'] == 'dorm')


def test_list_returns_user_schedules(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
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


def test_enable_follow_without_config_rejected(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        sid = _dorm_id(c, user_headers, acc_id)
        r = c.put(f'/api/schedules/{sid}', json={'enabled': True, 'mode': 'follow'}, headers=user_headers)
        assert r.status_code == 400
        assert r.get_json()['code'] == 4401
    finally:
        _delete_account(c, user_headers, acc_id)


def test_bind_nonexistent_config_set_rejected(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        sid = _dorm_id(c, user_headers, acc_id)
        r = c.put(f'/api/schedules/{sid}', json={'configSetId': 999999}, headers=user_headers)
        assert r.status_code == 400
        assert r.get_json()['code'] == 4400
    finally:
        _delete_account(c, user_headers, acc_id)


def test_invalid_custom_rejected(app, user_headers):
    c = app.test_client()
    acc_id = _create_account(c, user_headers)
    try:
        sid = _dorm_id(c, user_headers, acc_id)
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
        sid = _dorm_id(c, user_headers, acc_id)
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
        sid = _dorm_id(c, user_headers, acc_id)
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
        sid = _dorm_id(c, user_headers, acc_id)
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
        sid = _dorm_id(c, user_headers, acc_id)
        c.put(f'/api/schedules/{sid}',
              json={'enabled': True, 'mode': 'custom',
                    'custom': {'hour': 8, 'minute': 0, 'weekdays': [1]}},
              headers=user_headers)
        r2 = c.put(f'/api/schedules/{sid}', json={'enabled': False}, headers=user_headers)
        assert r2.status_code == 200
        assert r2.get_json()['data']['nextRunAt'] == ''
    finally:
        _delete_account(c, user_headers, acc_id)
