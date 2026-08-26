# backend/tests/test_config_set_default.py
# 模块 A：默认配置套唯一性（每用户至多一条 is_default）+ 种子保障
from app.extensions import db
from app.models import ConfigSet


def _cfg(weekdays=(1, 2, 3)):
    return {'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
                     'weekdays': list(weekdays), 'randomDelayMax': 5, 'mode': 'normal'},
            'remarks': ['签到'], 'image': {'enabled': False, 'strategy': 'recycle'},
            'push': {'channels': [], 'useOwnCredential': True, 'credIds': {}, 'cred': {}, 'notify': {}},
            'advanced': {'uaTemplateId': None, 'customUa': ''}}


def _me_uid(c, headers):
    return c.get('/api/auth/me', headers=headers).get_json()['data']['user_id']


def test_set_default_keeps_single(app, user_headers):
    c = app.test_client()
    uid = _me_uid(c, user_headers)
    r1 = c.post('/api/config-sets', json={'name': 'A', 'config': _cfg()}, headers=user_headers)
    r2 = c.post('/api/config-sets', json={'name': 'B', 'config': _cfg((4,))}, headers=user_headers)
    id1 = r1.get_json()['data']['id']
    id2 = r2.get_json()['data']['id']

    # 设 B 为默认
    c.put(f'/api/config-sets/{id2}', json={'isDefault': True}, headers=user_headers)
    sets = ConfigSet.query.filter_by(user_id=uid).all()
    assert sum(1 for s in sets if s.is_default) == 1
    assert ConfigSet.query.get(id2).is_default is True

    # 改设 A 为默认，B 应自动取消，仍仅一条默认
    c.put(f'/api/config-sets/{id1}', json={'isDefault': True}, headers=user_headers)
    assert ConfigSet.query.get(id1).is_default is True
    assert ConfigSet.query.get(id2).is_default is False
    assert sum(1 for s in ConfigSet.query.filter_by(user_id=uid).all() if s.is_default) == 1

    db.session.delete(ConfigSet.query.get(id1))
    db.session.delete(ConfigSet.query.get(id2))
    db.session.commit()


def test_seed_ensures_default(app, user_headers):
    c = app.test_client()
    uid = _me_uid(c, user_headers)
    # 启动种子已为该用户保障默认套：至少存在一条 is_default
    assert any(s.is_default for s in ConfigSet.query.filter_by(user_id=uid).all())
