# backend/tests/test_config_sets_api.py
from app.extensions import db
from app.models import ConfigSet


def _cfg(weekdays=(1, 2)):
    return {'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
                     'weekdays': list(weekdays), 'randomDelayMax': 5, 'mode': 'normal'},
            'remarks': ['签到'], 'image': {'enabled': False, 'strategy': 'recycle'},
            'push': {'channels': [], 'useOwnCredential': True, 'credIds': {}, 'cred': {}, 'notify': {}},
            'advanced': {'uaTemplateId': None, 'customUa': ''}}


def test_cycle(app, user_headers):
    c = app.test_client()
    r = c.post('/api/config-sets', json={'name': '标准套', 'config': _cfg()}, headers=user_headers)
    assert r.status_code == 201
    sid = r.get_json()['data']['id']

    items = c.get('/api/config-sets', headers=user_headers).get_json()['data']['items']
    assert any(s['id'] == sid and s['name'] == '标准套' for s in items)

    body = c.put(f'/api/config-sets/{sid}', json={'name': '标准套2', 'config': _cfg((7,))},
                 headers=user_headers).get_json()['data']
    assert body['name'] == '标准套2'
    assert body['config']['time']['weekdays'] == [7]

    # 401：无 token 一律拒绝
    assert app.test_client().get('/api/config-sets').status_code == 401

    db.session.delete(ConfigSet.query.get(sid))
    db.session.commit()


def test_validation_errors(app, user_headers):
    c = app.test_client()
    assert c.post('/api/config-sets', json={'config': {}}, headers=user_headers).status_code == 400
    bad = {'name': 'x', 'config': {'time': {'weekdays': [0]}, 'remarks': [], 'image': {}, 'push': {}, 'advanced': {}}}
    assert c.post('/api/config-sets', json=bad, headers=user_headers).status_code == 400
    assert c.delete('/api/config-sets/99999', headers=user_headers).status_code == 404
