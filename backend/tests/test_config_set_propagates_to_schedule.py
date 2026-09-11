# backend/tests/test_config_set_propagates_to_schedule.py
# 回归：配置套只是模板——修改并保存配置套，绝不回写已绑定任务实例。
# 账号任务配置保存改为「写入任务实例并解绑配置套」（快照复制模型）：
# 多账号共用同一配置套时，改一个账号的任务配置不会影响其他账号。
import os

os.environ['USE_STUB_BPLATFORM'] = '1'

import uuid


def _cfg(sign_hour, sign_minute, weekdays=(1, 2, 3, 4, 5, 6, 7)):
    return {'time': {'signTime': {'hour': sign_hour, 'minute': sign_minute},
                     'startHour': 8, 'endHour': 22, 'weekdays': list(weekdays),
                     'randomDelayMax': 5, 'mode': 'normal'},
            'remarks': ['签到'], 'image': {'enabled': False, 'strategy': 'recycle'},
            'push': {'channels': [], 'useOwnCredential': True, 'credIds': {}, 'cred': {}, 'notify': {}},
            'advanced': {'uaTemplateId': None, 'customUa': ''}}


def _create_account(c, headers):
    name = f'tc_{uuid.uuid4().hex[:12]}'
    r = c.post('/api/accounts', json={'account': name, 'password': 'x1', 'type': 'dorm'}, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()['data']['id']


def _get_schedule(c, headers, sched_id):
    items = c.get('/api/schedules', headers=headers).get_json()['data']['items']
    return next(s for s in items if s['id'] == sched_id)


def test_config_set_save_does_not_touch_bound_schedule(app, user_headers):
    """配置套改时间保存后，已绑定（快照复制）的任务实例的配置与下次执行不变。"""
    c = app.test_client()
    acc_id = None
    try:
        r = c.post('/api/config-sets', json={'name': '模板套', 'config': _cfg(21, 27)}, headers=user_headers)
        assert r.status_code == 201
        cs_id = r.get_json()['data']['id']

        # 绑定并启用：账号任务配置界面「套用」语义 = 复制配置进任务实例（standalone），保留源自标签
        acc_id = _create_account(c, user_headers)
        r = c.post('/api/schedules', json={'accountId': acc_id, 'taskType': 'dorm'}, headers=user_headers)
        assert r.status_code == 201
        sched_id = r.get_json()['data']['id']
        r = c.put(f'/api/schedules/{sched_id}',
                  json={'config': _cfg(21, 27), 'configSetId': cs_id, 'enabled': True},
                  headers=user_headers)
        assert r.status_code == 200

        sched = _get_schedule(c, user_headers, sched_id)
        assert '21:27' in sched['nextRunAt']
        assert sched['mode'] == 'standalone'
        assert sched['config']['time']['signTime'] == {'hour': 21, 'minute': 27}

        # 改配置套时间为 21:40 并保存（仅保存模板）
        r = c.put(f'/api/config-sets/{cs_id}',
                  json={'name': '模板套', 'config': _cfg(21, 40)}, headers=user_headers)
        assert r.status_code == 200

        # 任务实例应完全不受影响：配置与下次执行仍为 21:27
        sched = _get_schedule(c, user_headers, sched_id)
        assert '21:27' in sched['nextRunAt']
        assert '21:40' not in sched['nextRunAt']
        assert sched['config']['time']['signTime'] == {'hour': 21, 'minute': 27}
        # 配置套自身已更新（通过列表接口取回该套）
        items = c.get('/api/config-sets', headers=user_headers).get_json()['data']['items']
        cs = next(x for x in items if x['id'] == cs_id)
        assert cs['config']['time']['signTime'] == {'hour': 21, 'minute': 40}
    finally:
        # 清理（删账号级联删任务；删配置套防 tc_user 名下模板堆积）
        if acc_id:
            c.delete(f'/api/accounts/{acc_id}', headers=user_headers)
        c.delete(f'/api/config-sets/{cs_id}', headers=user_headers)


def test_schedule_save_writes_own_config_and_detaches(app, user_headers):
    """账号任务配置保存：写回任务实例（config_json），置 standalone 并解绑配置套。"""
    c = app.test_client()
    acc_id = None
    try:
        r = c.post('/api/config-sets', json={'name': '模板套', 'config': _cfg(21, 27)}, headers=user_headers)
        assert r.status_code == 201
        cs_id = r.get_json()['data']['id']

        acc_id = _create_account(c, user_headers)
        r = c.post('/api/schedules', json={'accountId': acc_id, 'taskType': 'dorm'}, headers=user_headers)
        assert r.status_code == 201
        sched_id = r.get_json()['data']['id']

        # 保存任务自身配置（21:40）并启用，显式解绑配置套（configSetId: null）
        own = _cfg(21, 40)
        r = c.put(f'/api/schedules/{sched_id}',
                  json={'config': own, 'configSetId': None, 'enabled': True}, headers=user_headers)
        assert r.status_code == 200
        sched = r.get_json()['data']
        assert sched['mode'] == 'standalone'
        assert sched['configSetId'] is None
        assert sched['config']['time']['signTime'] == {'hour': 21, 'minute': 40}
        assert '21:40' in sched['nextRunAt']

        # 之后改配置套时间，任务实例不受影响（互不影响）
        r = c.put(f'/api/config-sets/{cs_id}',
                  json={'name': '模板套', 'config': _cfg(7, 7)}, headers=user_headers)
        assert r.status_code == 200
        sched = _get_schedule(c, user_headers, sched_id)
        assert sched['config']['time']['signTime'] == {'hour': 21, 'minute': 40}
        assert '21:40' in sched['nextRunAt']
    finally:
        # 清理（删账号级联删任务；删配置套防 tc_user 名下模板堆积）
        if acc_id:
            c.delete(f'/api/accounts/{acc_id}', headers=user_headers)
        c.delete(f'/api/config-sets/{cs_id}', headers=user_headers)
