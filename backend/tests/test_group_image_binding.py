# 分组图库归属：分组侧读写 imageGroupId + 调度侧「按分组取图」的解析与回退链。
# 隔离策略同 test_checkin_flow：新建唯一用户，用后清空该用户全部关联数据。
import uuid

import pytest

from app.extensions import db
from app.models import BAccount, ImageGroup, PushGroup, PushGroupMember, Schedule, User
from app.services import scheduler as sch


def _cfg(image=None):
    cfg = {'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
                    'weekdays': [1, 2], 'randomDelayMax': 0, 'mode': 'normal'},
           'locationId': None, 'remarks': ['签到'],
           'image': image or {'enabled': False, 'strategy': 'recycle', 'groupId': None},
           'push': {}, 'advanced': {}, 'fence': {'intercept': True}}
    return cfg


class NeedPhotoAdapter:
    """任务需要图片，据此驱动图库认领分支"""

    def find_active_task(self, session, task_type):
        return {'task': {'id': 42, 'taskName': '07.02查寝签到', 'needPhoto': True,
                         'startTime': '00:00:00', 'endTime': '23:59:59'},
                'fence': []}

    def submit_checkin(self, *a, **k):
        raise AssertionError('未认领到图片时不应提交')


@pytest.fixture()
def own_headers(app_ctx):
    """独立用户 + token：本文件的接口用例不复用 tc_user。
    tc_user 的图库分组被 test_pools_images_api 断言为「只有一个/为空」，
    共用会让两边互相污染（失败时残留分组会把对方带崩）。"""
    from app.utils.auth import generate_token

    uname = f'tc_gimg_api_{uuid.uuid4().hex[:10]}'
    u = User(username=uname, role='user', enabled=True, quota=100, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    uid = u.id
    yield {'uid': uid, 'headers': {'Authorization': f'Bearer {generate_token(u)}'}}

    gids = [g.id for g in PushGroup.query.filter_by(user_id=uid).all()]
    if gids:
        PushGroupMember.query.filter(PushGroupMember.group_id.in_(gids)) \
            .delete(synchronize_session=False)
    PushGroup.query.filter_by(user_id=uid).delete(synchronize_session=False)
    ImageGroup.query.filter_by(user_id=uid).delete(synchronize_session=False)
    db.session.delete(db.session.get(User, uid))
    db.session.commit()


@pytest.fixture()
def bind_env(app_ctx):
    """唯一用户 + 账号 + 两个图库分组；返回 uid / acc / a / b（a、b 为图库分组 id）"""
    uname = f'tc_gimg_{uuid.uuid4().hex[:10]}'
    u = User(username=uname, role='user', enabled=True, quota=100, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    acc = BAccount(user_id=u.id, account=f'acc_{uname}', password_enc='x')
    img_a = ImageGroup(user_id=u.id, name='3栋507')
    img_b = ImageGroup(user_id=u.id, name='3栋508')
    db.session.add_all([acc, img_a, img_b])
    db.session.commit()

    uid = u.id
    yield {'uid': uid, 'acc': acc, 'a': img_a.id, 'b': img_b.id}

    gids = [g.id for g in PushGroup.query.filter_by(user_id=uid).all()]
    if gids:
        PushGroupMember.query.filter(PushGroupMember.group_id.in_(gids)) \
            .delete(synchronize_session=False)
    PushGroup.query.filter_by(user_id=uid).delete(synchronize_session=False)
    ImageGroup.query.filter_by(user_id=uid).delete(synchronize_session=False)
    BAccount.query.filter_by(user_id=uid).delete(synchronize_session=False)
    db.session.delete(db.session.get(User, uid))
    db.session.commit()


def _dorm_group(uid, name, image_group_id=None, accounts=()):
    g = PushGroup(user_id=uid, type=PushGroup.TYPE_DORM, name=name,
                  image_group_id=image_group_id)
    db.session.add(g)
    db.session.flush()
    for acc in accounts:
        db.session.add(PushGroupMember(group_id=g.id, account_id=acc.id))
    db.session.commit()
    return g


# ───────────────────────── 分组接口读写图库归属 ─────────────────────────

def test_dorm_group_image_binding_crud(app, own_headers):
    """寝室分组：建组即可带图库，PUT 可改可解绑，非本人图库一律拒绝"""
    c = app.test_client()
    headers = own_headers['headers']
    name = f'测试寝室_{uuid.uuid4().hex[:8]}'
    r = c.post('/api/pools/image-groups', json={'name': '3栋507'}, headers=headers)
    img_id = r.get_json()['data']['id']

    r = c.post('/api/group-push/groups', json={'name': name, 'imageGroupId': img_id},
               headers=headers)
    assert r.status_code == 201, r.get_json()
    gid = r.get_json()['data']['id']
    assert r.get_json()['data']['imageGroupId'] == img_id
    assert r.get_json()['data']['bound'] is False  # 未绑 QQ 群，与图库归属互不影响

    # 单独改图库归属不需要带 name；可解绑、可再绑
    r = c.put(f'/api/group-push/groups/{gid}', json={'imageGroupId': None}, headers=headers)
    assert r.get_json()['data']['imageGroupId'] is None
    r = c.put(f'/api/group-push/groups/{gid}', json={'imageGroupId': img_id}, headers=headers)
    assert r.get_json()['data']['imageGroupId'] == img_id

    # 越权：不是自己名下的图库 id 一律拒绝
    r = c.put(f'/api/group-push/groups/{gid}', json={'imageGroupId': 1}, headers=headers)
    assert r.status_code == 400, r.get_json()

    # 列表带出图库归属
    items = c.get('/api/group-push/groups', query_string={'type': 'dorm'},
                  headers=headers).get_json()['data']['items']
    assert next(x for x in items if x['id'] == gid)['imageGroupId'] == img_id


def test_class_group_image_only_binding_keeps_row(app, own_headers):
    """班级分组只绑图库（不绑 QQ 群）时必须留行：整行删掉会让图库归属没处存。
    两者皆空才算彻底解绑，此时删行。"""
    c = app.test_client()
    headers = own_headers['headers']
    name = f'测试班级_{uuid.uuid4().hex[:8]}'
    r = c.post('/api/pools/image-groups', json={'name': '3栋507'}, headers=headers)
    img_id = r.get_json()['data']['id']
    r = c.post('/api/group-push/class-bind', json={'name': name, 'imageGroupId': img_id},
               headers=headers)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['data']['imageGroupId'] == img_id
    row = PushGroup.query.filter_by(type=PushGroup.TYPE_CLASS, name=name).first()
    assert row is not None and row.image_group_id == img_id and row.qq_code is None

    # 只传 qqCode 时图库归属不动：两处局部保存不能互相冲掉
    c.post('/api/group-push/class-bind', json={'name': name, 'qqCode': 'dorm-test'},
           headers=headers)
    db.session.expire_all()
    row = PushGroup.query.filter_by(type=PushGroup.TYPE_CLASS, name=name).first()
    assert row.qq_code == 'dorm-test' and row.image_group_id == img_id

    # 只解绑图库：QQ 群还在，行必须保留
    c.post('/api/group-push/class-bind',
           json={'name': name, 'qqCode': 'dorm-test', 'imageGroupId': ''},
           headers=headers)
    db.session.expire_all()
    row = PushGroup.query.filter_by(type=PushGroup.TYPE_CLASS, name=name).first()
    assert row is not None and row.image_group_id is None and row.qq_code == 'dorm-test'

    # 两者皆空：整行删除
    c.post('/api/group-push/class-bind', json={'name': name, 'qqCode': ''}, headers=headers)
    assert PushGroup.query.filter_by(type=PushGroup.TYPE_CLASS, name=name).first() is None


# ───────────────────────── 取图范围解析 ─────────────────────────

def test_resolve_fixed_mode_uses_configured_group(bind_env):
    env = bind_env
    cfg = _cfg({'enabled': True, 'strategy': 'recycle', 'groupId': env['b']})
    assert sch.resolve_image_group(env['uid'], cfg, env['acc']) == env['b']


def test_resolve_by_group_prefers_group_binding(bind_env):
    env = bind_env
    _dorm_group(env['uid'], '507', image_group_id=env['a'], accounts=[env['acc']])
    cfg = _cfg({'enabled': True, 'strategy': 'recycle', 'mode': 'byGroup',
                'groupKind': 'dorm', 'groupId': env['b']})
    # 分组已绑图库 → 用分组绑定的，忽略配置套默认图库
    assert sch.resolve_image_group(env['uid'], cfg, env['acc']) == env['a']


def test_resolve_by_group_falls_back_when_unbound_or_absent(bind_env):
    env = bind_env
    cfg = _cfg({'enabled': True, 'strategy': 'recycle', 'mode': 'byGroup',
                'groupKind': 'dorm', 'groupId': env['b']})
    # 账号不在任何分组
    assert sch.resolve_image_group(env['uid'], cfg, env['acc']) == env['b']
    # 在分组里但分组没绑图库
    _dorm_group(env['uid'], '507', image_group_id=None, accounts=[env['acc']])
    assert sch.resolve_image_group(env['uid'], cfg, env['acc']) == env['b']
    # 默认图库也没配 → 回退全部图库
    cfg2 = _cfg({'enabled': True, 'strategy': 'recycle', 'mode': 'byGroup',
                 'groupKind': 'dorm', 'groupId': ''})
    assert sch.resolve_image_group(env['uid'], cfg2, env['acc']) is None


def test_resolve_by_group_class_kind_matches_class_name(bind_env):
    env = bind_env
    env['acc'].set_profile({'className': '计科2301'})
    db.session.commit()
    cls_group = PushGroup(user_id=env['uid'], type=PushGroup.TYPE_CLASS, name='计科2301',
                          image_group_id=env['a'])
    db.session.add(cls_group)
    db.session.commit()
    cfg = _cfg({'enabled': True, 'strategy': 'recycle', 'mode': 'byGroup',
                'groupKind': 'class', 'groupId': env['b']})
    assert sch.resolve_image_group(env['uid'], cfg, env['acc']) == env['a']
    # 换成按寝室分组：班级归属不参与，回退默认图库
    cfg['image']['groupKind'] = 'dorm'
    assert sch.resolve_image_group(env['uid'], cfg, env['acc']) == env['b']


def test_resolve_by_group_ignores_dangling_binding(bind_env):
    """分组指向的图库不属于本人（脏数据）时不吃这条绑定，回退默认图库"""
    env = bind_env
    other_user = User(username=f'tc_gimg_x_{uuid.uuid4().hex[:8]}', role='user',
                      enabled=True, quota=100, used_quota=0)
    other_user.set_password('pw')
    db.session.add(other_user)
    db.session.flush()
    other = ImageGroup(user_id=other_user.id, name='他机图库')
    db.session.add(other)
    db.session.commit()
    other_id, other_uid = other.id, other_user.id
    try:
        _dorm_group(env['uid'], '507', image_group_id=other_id, accounts=[env['acc']])
        cfg = _cfg({'enabled': True, 'strategy': 'recycle', 'mode': 'byGroup',
                    'groupKind': 'dorm', 'groupId': env['b']})
        assert sch.resolve_image_group(env['uid'], cfg, env['acc']) == env['b']
    finally:
        ImageGroup.query.filter_by(user_id=other_uid).delete(synchronize_session=False)
        db.session.delete(db.session.get(User, other_uid))
        db.session.commit()


# ───────────────────────── 快照与提交链路 ─────────────────────────

def test_config_snapshot_records_effective_group(bind_env):
    """执行时快照要写实际命中的图库，否则事后只看到默认图库，无从判断取错图的原因"""
    env = bind_env
    _dorm_group(env['uid'], '507', image_group_id=env['a'], accounts=[env['acc']])
    sched = Schedule(user_id=env['uid'], account_id=env['acc'].id, task_type='dorm',
                     mode='standalone', enabled=True)
    cfg = _cfg({'enabled': True, 'strategy': 'recycle', 'mode': 'byGroup',
                'groupKind': 'dorm', 'groupId': env['b']})
    view = sch.build_config_view(sched, cfg, env['uid'], acc=env['acc'])
    assert view['image']['mode'] == 'byGroup'
    assert view['image']['groupId'] == env['a']
    assert view['image']['groupName'] == '3栋507'

    # 固定图库：不查分组，直接记配置值
    cfg_fixed = _cfg({'enabled': True, 'strategy': 'recycle', 'groupId': env['b']})
    view = sch.build_config_view(sched, cfg_fixed, env['uid'], acc=env['acc'])
    assert view['image']['mode'] == 'fixed'
    assert view['image']['groupName'] == '3栋508'


@pytest.mark.parametrize('kind', ['dorm', 'class'])
def test_checkin_flow_claims_from_resolved_group(bind_env, monkeypatch, kind):
    """_checkin_flow 必须用解析后的图库认领，而不是配置套里的默认图库"""
    env = bind_env
    if kind == 'class':
        env['acc'].set_profile({'className': '计科2301'})
        db.session.commit()
        group = PushGroup(user_id=env['uid'], type=PushGroup.TYPE_CLASS, name='计科2301',
                          image_group_id=env['a'])
        db.session.add(group)
        db.session.commit()
    else:
        _dorm_group(env['uid'], '507', image_group_id=env['a'], accounts=[env['acc']])

    captured = {}

    def fake_claim(uid, group_id, strategy):
        captured['group'] = group_id
        return None

    monkeypatch.setattr(sch, 'claim_image_for_submit', fake_claim)
    monkeypatch.setattr(sch, 'get_adapter', lambda: NeedPhotoAdapter())
    sched = Schedule(user_id=env['uid'], account_id=env['acc'].id, task_type='dorm',
                     mode='standalone', enabled=True)
    cfg = _cfg({'enabled': True, 'strategy': 'recycle', 'mode': 'byGroup',
                'groupKind': kind, 'groupId': env['b']})
    outcome, reason, _ = sch._checkin_flow(sched, env['acc'], {'token': 't', 'ua': None},
                                           cfg, '签到')
    assert captured['group'] == env['a']
    assert outcome == 'fail' and '图库暂无可用图片' in reason


def test_checkin_flow_need_photo_without_library_fails_fast(bind_env, monkeypatch):
    env = bind_env
    monkeypatch.setattr(sch, 'get_adapter', lambda: NeedPhotoAdapter())
    sched = Schedule(user_id=env['uid'], account_id=env['acc'].id, task_type='dorm',
                     mode='standalone', enabled=True)
    cfg = _cfg({'enabled': False, 'strategy': 'recycle', 'groupId': None})
    outcome, reason, _ = sch._checkin_flow(sched, env['acc'], {'token': 't', 'ua': None},
                                           cfg, '签到')
    assert outcome == 'fail' and '需要上传签到图片' in reason


# ───────────────────────── 寝室分组成员地图 ─────────────────────────

def test_dorm_members_map_covers_all_groups(app, bind_env, request):
    """成员地图一次返回所有寝室的 (accountId, 分组)：账号卡片靠它标注所属分组。
    他人的分组与成员不得泄漏；删组即断归属。"""
    env = bind_env
    uid = env['uid']
    c = app.test_client()

    tag = uuid.uuid4().hex[:8]
    extra = [BAccount(user_id=uid, account=f'gmap_{tag}_{i}', password_enc='x') for i in range(2)]
    db.session.add_all(extra)
    db.session.flush()

    # 他人的分组与成员：本用例自己造、自己删（bind_env 的清理只覆盖 env['uid']）
    other = User(username=f'tc_gmap_other_{tag}', role='user', enabled=True,
                 quota=100, used_quota=0)
    other.set_password('pw')
    db.session.add(other)
    db.session.flush()
    alien = BAccount(user_id=other.id, account=f'gmap_alien_{tag}', password_enc='x')
    db.session.add(alien)
    db.session.commit()

    def _drop_other():
        gids = [g.id for g in PushGroup.query.filter_by(user_id=other.id).all()]
        if gids:
            PushGroupMember.query.filter(PushGroupMember.group_id.in_(gids)) \
                .delete(synchronize_session=False)
        PushGroup.query.filter_by(user_id=other.id).delete(synchronize_session=False)
        BAccount.query.filter_by(user_id=other.id).delete(synchronize_session=False)
        db.session.delete(db.session.get(User, other.id))
        db.session.commit()

    request.addfinalizer(_drop_other)

    g1 = _dorm_group(uid, f'507_{tag}', accounts=[env['acc'], extra[0]])
    g2 = _dorm_group(uid, f'508_{tag}', accounts=[extra[1]])
    _dorm_group(other.id, f'他人的组_{tag}', accounts=[alien])

    from app.utils.auth import generate_token

    headers = {'Authorization': f'Bearer {generate_token(db.session.get(User, uid))}'}
    items = c.get('/api/group-push/dorm-members', headers=headers).get_json()['data']['items']
    got = {(x['accountId'], x['groupName']) for x in items}
    assert (env['acc'].id, g1.name) in got
    assert (extra[0].id, g1.name) in got
    assert (extra[1].id, g2.name) in got
    assert len([x for x in items if x['accountId'] == env['acc'].id]) == 1
    assert all(x['accountId'] != alien.id for x in items)

    # 删组即断归属：地图不应再出现该组成员
    r = c.delete(f'/api/group-push/groups/{g2.id}', headers=headers)
    assert r.status_code == 200, r.get_json()
    items = c.get('/api/group-push/dorm-members', headers=headers).get_json()['data']['items']
    assert all(x['accountId'] != extra[1].id for x in items)
