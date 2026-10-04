# 审计 T1/T2 回归：
# T1——删除配置套不得让启用中的 follow 任务变成「配置孤儿」（原实现直接把
#     config_set_id 置空，follow 任务无自持配置，保持启用只会每次执行都失败）。
#     现行为：follow 启用任务自动停用并反馈；standalone 任务仅摘除来源标签，不受影响。
# T2——批量接口对非整数 accountId 直接 int() 会未捕获 ValueError → 500；
#     现行为：非法项静默跳过，有效项照常处理。
import os

os.environ['USE_STUB_BPLATFORM'] = '1'

import uuid

from app.extensions import db
from app.models import Schedule


def _cfg(sign_hour=8, sign_minute=30):
    return {'time': {'signTime': {'hour': sign_hour, 'minute': sign_minute},
                     'startHour': 8, 'endHour': 22, 'weekdays': [1, 2, 3, 4, 5, 6, 7],
                     'randomDelayMax': 5, 'mode': 'normal'},
            'remarks': ['签到'], 'image': {'enabled': False, 'strategy': 'recycle'},
            'push': {'channels': [], 'useOwnCredential': True, 'credIds': {}, 'cred': {}, 'notify': {}},
            'advanced': {'uaTemplateId': None, 'customUa': ''}}


def _create_account(c, headers):
    name = f'tc_{uuid.uuid4().hex[:12]}'
    r = c.post('/api/accounts', json={'account': name, 'password': 'x1', 'type': 'dorm'},
               headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()['data']['id']


def _create_set(c, headers, name='审计套'):
    r = c.post('/api/config-sets', json={'name': name, 'config': _cfg()}, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()['data']['id']


def _get_schedule(c, headers, sched_id):
    items = c.get('/api/schedules', headers=headers).get_json()['data']['items']
    return next(s for s in items if s['id'] == sched_id)


def test_t1_delete_set_disables_enabled_follow_schedule(app, user_headers):
    """删除被启用中 follow 任务引用的配置套：任务自动停用（而非留下必败的孤儿），响应带明细。"""
    c = app.test_client()
    acc_id = None
    try:
        cs_id = _create_set(c, user_headers)
        acc_id = _create_account(c, user_headers)
        r = c.post('/api/schedules', json={'accountId': acc_id, 'taskType': 'dorm'},
                   headers=user_headers)
        sched_id = r.get_json()['data']['id']

        # 纯绑定（仅 configSetId，无 config）→ follow 模式并启用
        r = c.put(f'/api/schedules/{sched_id}',
                  json={'configSetId': cs_id, 'enabled': True}, headers=user_headers)
        assert r.status_code == 200, r.get_json()
        assert _get_schedule(c, user_headers, sched_id)['mode'] == 'follow'
        assert _get_schedule(c, user_headers, sched_id)['enabled'] is True

        r = c.delete(f'/api/config-sets/{cs_id}', headers=user_headers)
        assert r.status_code == 200
        assert r.get_json()['data']['disabledFollowCount'] == 1

        sched = _get_schedule(c, user_headers, sched_id)
        assert sched['enabled'] is False, 'follow 任务必须随配置套删除自动停用'
        assert not sched['nextRunAt'], '停用后 next_run_at 必须清空'
    finally:
        if acc_id:
            c.delete(f'/api/accounts/{acc_id}', headers=user_headers)


def test_t1_delete_set_keeps_standalone_snapshot(app, user_headers):
    """删除配置套不影响 standalone 任务：自持快照原样保留，仅来源标签被摘除。"""
    c = app.test_client()
    acc_id = None
    try:
        cs_id = _create_set(c, user_headers)
        acc_id = _create_account(c, user_headers)
        sched_id = c.post('/api/schedules',
                          json={'accountId': acc_id, 'taskType': 'dorm'},
                          headers=user_headers).get_json()['data']['id']

        # 套用配置（带 config + configSetId）→ standalone 快照 + 来源标签
        r = c.put(f'/api/schedules/{sched_id}',
                  json={'config': _cfg(21, 27), 'configSetId': cs_id, 'enabled': True},
                  headers=user_headers)
        assert r.status_code == 200

        r = c.delete(f'/api/config-sets/{cs_id}', headers=user_headers)
        assert r.status_code == 200
        assert r.get_json()['data']['disabledFollowCount'] == 0

        sched = _get_schedule(c, user_headers, sched_id)
        assert sched['enabled'] is True, 'standalone 任务自持配置，删除来源套不受影响'
        assert sched['mode'] == 'standalone'
        assert sched['configSetId'] is None
        assert sched['config']['time']['signTime'] == {'hour': 21, 'minute': 27}
        assert '21:27' in sched['nextRunAt']
    finally:
        if acc_id:
            c.delete(f'/api/accounts/{acc_id}', headers=user_headers)


def test_t1_disabled_follow_schedule_stays_disabled_after_set_delete(app, user_headers):
    """已停用的 follow 任务删除配置套后保持停用（enabled=False 不被误改，也不记入停用明细）。"""
    c = app.test_client()
    acc_id = None
    try:
        cs_id = _create_set(c, user_headers)
        acc_id = _create_account(c, user_headers)
        sched_id = c.post('/api/schedules',
                          json={'accountId': acc_id, 'taskType': 'dorm'},
                          headers=user_headers).get_json()['data']['id']
        # 纯 follow 绑定但不开启
        r = c.put(f'/api/schedules/{sched_id}', json={'configSetId': cs_id},
                  headers=user_headers)
        assert r.status_code == 200

        r = c.delete(f'/api/config-sets/{cs_id}', headers=user_headers)
        assert r.status_code == 200
        assert r.get_json()['data']['disabledFollowCount'] == 0
        assert _get_schedule(c, user_headers, sched_id)['enabled'] is False
    finally:
        if acc_id:
            c.delete(f'/api/accounts/{acc_id}', headers=user_headers)


def test_t2_batch_manage_skips_non_numeric_account_id(app, user_headers):
    """batch_manage 对 accountId='abc' 不再 500：非法项跳过，有效项照常处理。"""
    c = app.test_client()
    acc_id = None
    try:
        acc_id = _create_account(c, user_headers)
        # 先创建任务实例并保持停用，disable 场景下它会被计入 skipped（未启用）
        c.post('/api/schedules', json={'accountId': acc_id, 'taskType': 'dorm'},
               headers=user_headers)

        r = c.post('/api/schedules/batch-manage',
                   json={'action': 'disable',
                         'targets': [{'accountId': 'abc', 'taskType': 'dorm'},
                                     {'accountId': acc_id, 'taskType': 'dorm'}]},
                   headers=user_headers)
        assert r.status_code == 200, r.get_json()
        body = r.get_json()['data']
        # 非法 accountId 在去重阶段被过滤（从未成为有效目标，与 apply-batch 口径一致），
        # 只有「未启用任务」计入 skipped
        assert body['affected'] == 0 and body['skipped'] == 1
    finally:
        if acc_id:
            c.delete(f'/api/accounts/{acc_id}', headers=user_headers)


def test_t2_apply_batch_skips_non_numeric_account_id(app, user_headers):
    """apply-batch 对 accountId='abc' 不再 500：合法项正常套用。"""
    c = app.test_client()
    acc_id = None
    try:
        cs_id = _create_set(c, user_headers)
        acc_id = _create_account(c, user_headers)

        r = c.post(f'/api/config-sets/{cs_id}/apply-batch',
                   json={'targets': [{'accountId': 'abc', 'taskType': 'dorm'},
                                     {'accountId': acc_id, 'taskType': 'dorm'}]},
                   headers=user_headers)
        assert r.status_code == 200, r.get_json()
        body = r.get_json()['data']
        # 'abc' 被过滤（不计入 skipped 计数——它从未成为有效目标），合法项照常套用
        assert body['updated'] == 1 and body['skipped'] == 0
    finally:
        if acc_id:
            c.delete(f'/api/accounts/{acc_id}', headers=user_headers)
