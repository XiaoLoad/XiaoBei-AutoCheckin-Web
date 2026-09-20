# 认领链路的 recycle 轮回：`used` 只是「本轮内别重复用同一张」的暂存态，active 取尽即整批
# 回池重新随机。回归场景：寝室分组 6 人、绑定图库只剩 4 张 active、策略 recycle ——
# 此前接了回池的是另一条消费链路、真实认领链路漏接，导致第 5、6 人直接判「图库暂无可用图片」。
import os
import uuid

import pytest

from app.extensions import db
from app.models import (BAccount, ImageGroup, PoolImage, PushGroup, PushGroupMember,
                        Schedule, User)
from app.services import scheduler as sch
from app.services.b_platform.base import CheckinResult
from app.services.image_store import claim_image_for_submit, rollback_claim, user_dir

IMAGE_BYTES = b'\xff\xd8' + b'x' * 64   # 内容不重要，认领只要求文件能读出字节


def _cfg(image=None):
    return {'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
                     'weekdays': [1, 2, 3, 4, 5], 'randomDelayMax': 0, 'mode': 'normal'},
            'locationId': None, 'remarks': ['签到'],
            'image': image or {'enabled': False, 'strategy': 'recycle', 'groupId': None},
            'push': {}, 'advanced': {}, 'fence': {'intercept': True}}


@pytest.fixture()
def img_env(app_ctx, tmp_path):
    """唯一用户 + 图库分组；真文件落 tmp_path（认领要读字节，文件缺失会被当成读失败换下一张）。"""
    app_ctx.config['UPLOAD_DIR'] = str(tmp_path)
    uname = f'tc_reclaim_{uuid.uuid4().hex[:10]}'
    u = User(username=uname, role='user', enabled=True, quota=100, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    g = ImageGroup(user_id=u.id, name='3栋827')
    db.session.add(g)
    db.session.commit()

    uid, gid = u.id, g.id
    yield {'uid': uid, 'gid': gid}

    gids = [x.id for x in PushGroup.query.filter_by(user_id=uid).all()]
    if gids:
        PushGroupMember.query.filter(PushGroupMember.group_id.in_(gids)) \
            .delete(synchronize_session=False)
    for model in (PoolImage, PushGroup, Schedule, ImageGroup, BAccount):
        model.query.filter_by(user_id=uid).delete(synchronize_session=False)
    db.session.delete(db.session.get(User, uid))
    db.session.commit()


def _mk_images(user_id, n, group_id=None, status='active'):
    """造 n 张图并落真实文件。"""
    rows = []
    for i in range(n):
        img = PoolImage(user_id=user_id, group_id=group_id, orig_name=f'p{i}.jpg',
                        filename=f'f{i}_{uuid.uuid4().hex[:6]}.jpg', size=1024,
                        mime='image/jpeg', status=status)
        db.session.add(img)
        rows.append(img)
    db.session.commit()
    d = user_dir(user_id)
    for img in rows:
        with open(os.path.join(d, img.filename), 'wb') as f:
            f.write(IMAGE_BYTES)
    return sorted(r.id for r in rows)


def _reload(img_id):
    db.session.expire_all()
    return db.session.get(PoolImage, img_id)


def _counts(user_id, group_id=None):
    """(active, used) 计数；走 expire_all 避免 ORM 缓存脏读（流转是原生 UPDATE）。"""
    db.session.expire_all()
    q = PoolImage.query.filter_by(user_id=user_id)
    if group_id is not None:
        q = q.filter_by(group_id=group_id)
    return (q.filter_by(status='active').count(), q.filter_by(status='used').count())


# ───────────────────────── 回归：图不够时回池复用 ─────────────────────────

def test_four_images_serve_six_members(img_env):
    """回归核心：4 张图、6 人依次认领，6 次都必须取到图，且前 4 人各用一张不同的。"""
    env = img_env
    ids = _mk_images(env['uid'], 4, group_id=env['gid'])

    got = []
    for _ in range(6):
        r = claim_image_for_submit(env['uid'], env['gid'], 'recycle')
        assert r is not None, 'recycle 应回池复用，不该判无图'
        assert r['bytes'] == IMAGE_BYTES, '认领必须带出该图的真实字节'
        got.append(r['id'])

    assert sorted(got[:4]) == ids       # 一轮内互不重复——used 的用途就是这个
    assert set(got[4:]) <= set(ids)     # 图不够时才从回池的图里随机复用
    assert len(set(got)) == 4           # 只有 4 张图，不可能凭空多出第 5 张


def test_reclaim_is_batch_and_resets_used(img_env):
    """回池是「整批」：取尽后 used 全部转回 active，本次认领的那张再转回 used。"""
    env = img_env
    ids = _mk_images(env['uid'], 3, group_id=env['gid'])
    for _ in ids:
        assert claim_image_for_submit(env['uid'], env['gid'], 'recycle') is not None
    assert _counts(env['uid'], env['gid']) == (0, 3)      # 一轮用完：active=0 used=3

    again = claim_image_for_submit(env['uid'], env['gid'], 'recycle')
    assert again['id'] in ids
    assert _counts(env['uid'], env['gid']) == (2, 1)      # 3 张回池，本次又占走 1 张
    assert all(_reload(i).trashed_at is None for i in ids)  # recycle 不落回收站


def test_reclaim_stays_within_scope(img_env):
    """回池只作用于该取图范围：组外的 used 不能被顺手捞回，组外 active 也不受影响。"""
    env = img_env
    outside_used = _mk_images(env['uid'], 1, status='used')
    outside_active = _mk_images(env['uid'], 1)
    in_group = _mk_images(env['uid'], 2, group_id=env['gid'])

    got = [claim_image_for_submit(env['uid'], env['gid'], 'recycle') for _ in range(3)]

    assert all(r is not None for r in got)                 # 第 3 次靠回池拿到
    assert {r['id'] for r in got} <= set(in_group)
    assert _reload(outside_used[0]).status == 'used'       # 组外的 used 不被回池带入
    assert _reload(outside_active[0]).status == 'active'


def test_reclaim_ignores_trashed_images(img_env):
    """回收站里的图不参与轮回：回池只动 used，不把 trash 捞回来。"""
    env = img_env
    trashed = _mk_images(env['uid'], 1, status='trash')
    _mk_images(env['uid'], 2)

    for _ in range(3):
        assert claim_image_for_submit(env['uid'], None, 'recycle') is not None

    assert _reload(trashed[0]).status == 'trash'


def test_rollback_then_reclaim_still_claims(img_env):
    """提交失败回滚的图能立刻被再抽到；与回池机制共存不打架。"""
    env = img_env
    ids = _mk_images(env['uid'], 1, group_id=env['gid'])

    first = claim_image_for_submit(env['uid'], env['gid'], 'recycle')
    assert first['id'] == ids[0] and _reload(ids[0]).status == 'used'
    assert rollback_claim(first['id'], env['uid'], 'recycle') is True
    assert _reload(ids[0]).status == 'active'

    again = claim_image_for_submit(env['uid'], env['gid'], 'recycle')
    assert again['id'] == ids[0]


# ───────────────────────── 非 recycle 策略不回池（语义不变） ─────────────────────────

def test_trash_strategy_never_reclaims(img_env):
    env = img_env
    ids = _mk_images(env['uid'], 2, group_id=env['gid'])

    assert claim_image_for_submit(env['uid'], env['gid'], 'trash') is not None
    assert claim_image_for_submit(env['uid'], env['gid'], 'trash') is not None
    assert claim_image_for_submit(env['uid'], env['gid'], 'trash') is None   # 池空即无图
    assert all(_reload(i).status == 'trash' for i in ids)
    assert all(_reload(i).trashed_at is not None for i in ids)


def test_delete_strategy_never_reclaims(img_env):
    """delete 策略：认领即物理删除、不回池；返回值字段须完整。

    回归：删除分支在 commit 后还去读 ORM 对象的字段，对象已过期且行已删，惰性刷新
    必然抛 ObjectDeletedError —— 该分支此前无任何测试覆盖，等于 delete 策略下签到必崩。"""
    env = img_env
    ids = _mk_images(env['uid'], 2, group_id=env['gid'])

    first = claim_image_for_submit(env['uid'], env['gid'], 'delete')
    assert first is not None
    assert first['id'] in ids
    assert first['bytes'] == IMAGE_BYTES
    assert first['mime'] == 'image/jpeg' and first['orig_name'].endswith('.jpg')

    assert claim_image_for_submit(env['uid'], env['gid'], 'delete') is not None
    assert claim_image_for_submit(env['uid'], env['gid'], 'delete') is None
    # 记录已物理删除：用 SQL 计数核对，别走 session.get()——行已删时刷新失效的
    # identity map 条目同样会抛 ObjectDeletedError
    db.session.expire_all()
    assert PoolImage.query.filter(PoolImage.id.in_(ids)).count() == 0


def test_unknown_strategy_falls_back_to_trash(img_env):
    """未知策略按 trash 处理（可恢复，避免误删），同样不回池。"""
    env = img_env
    ids = _mk_images(env['uid'], 1, group_id=env['gid'])
    assert claim_image_for_submit(env['uid'], env['gid'], 'bogus') is not None
    assert _reload(ids[0]).status == 'trash'
    assert claim_image_for_submit(env['uid'], env['gid'], 'bogus') is None


# ───────────────────────── 确实无图时仍判无图 ─────────────────────────

def test_empty_library_returns_none(img_env):
    env = img_env
    assert claim_image_for_submit(env['uid'], env['gid'], 'recycle') is None


def test_only_trashed_images_returns_none(img_env):
    """回池捞不到东西（只有回收站图）时不能假装成功。"""
    env = img_env
    _mk_images(env['uid'], 2, group_id=env['gid'], status='trash')
    assert claim_image_for_submit(env['uid'], env['gid'], 'recycle') is None


# ───────────────────────── 端到端：6 人走真实 _checkin_flow 全成功 ─────────────────────────

class _PhotoAdapter:
    """需要图片的任务；提交一律成功，并记录提交次数。"""

    def __init__(self):
        self.submits = 0

    def find_active_task(self, session, task_type):
        return {'task': {'id': 42, 'taskName': '07.02查寝签到', 'needPhoto': True,
                         'startTime': '00:00:00', 'endTime': '23:59:59'}, 'fence': []}

    def submit_checkin(self, session, task_type, task_id, location_str, address,
                       remark, image):
        self.submits += 1
        assert image and image.get('bytes'), '需要图片的任务必须带图提交'
        return CheckinResult(ok=True, status='success', detail={'rsp': {'code': 0}})


def test_six_members_all_succeed_end_to_end(img_env, monkeypatch):
    """端到端：4 张图、分组 6 人走真实 _checkin_flow 全部 success（此前后 2 人 fail）。"""
    env = img_env
    uid = env['uid']
    ids = _mk_images(uid, 4, group_id=env['gid'])

    acc = BAccount(user_id=uid, account=f'acc_{uuid.uuid4().hex[:8]}', password_enc='x')
    db.session.add(acc)
    db.session.flush()
    group = PushGroup(user_id=uid, type=PushGroup.TYPE_DORM, name='507',
                      image_group_id=env['gid'])
    db.session.add(group)
    db.session.flush()
    db.session.add(PushGroupMember(group_id=group.id, account_id=acc.id))
    db.session.commit()

    adapter = _PhotoAdapter()
    monkeypatch.setattr(sch, 'get_adapter', lambda: adapter)
    # byGroup + 分组已绑图库：默认图库留空，取图范围由分组绑定决定（与线上口径一致）
    cfg = _cfg({'enabled': True, 'strategy': 'recycle', 'mode': 'byGroup',
                'groupKind': 'dorm', 'groupId': None})

    claimed_ids = []
    for i in range(6):
        sched = Schedule(user_id=uid, account_id=acc.id, task_type='dorm',
                         mode='standalone', enabled=True)
        outcome, reason, extra = sch._checkin_flow(sched, acc, {'token': 't', 'ua': None},
                                                   cfg, '签到')
        assert outcome == 'success', f'第 {i + 1} 人：{reason}'
        assert extra.get('image_group_id') == env['gid']    # 图库按分组绑定解析
        claimed_ids.append(extra.get('image_id'))

    assert adapter.submits == 6
    assert all(i is not None for i in claimed_ids)
    assert sorted(claimed_ids[:4]) == ids                   # 前 4 人各一张不同的
    assert set(claimed_ids[4:]) <= set(ids)                 # 后 2 人从回池的图里复用
    assert _counts(uid, env['gid']) == (2, 2)               # 4 张图轮转：第 5 人触发回池


# ───────────────────── 第 ⑤ 步：取图一律以配置项 image.enabled 为准 ─────────────────────
#
# 语义：配置未启用图库 → 不取图、不上传，只有平台任务确实要求图片时才判失败；
# 配置启用 → 取一张附上。但取不到图时只有 needPhoto 为真才判失败，任务并不要求图片的
# 降级为无图提交——否则一个本来不需要图就能签到的任务，会仅仅因为图库空了而失败。

class _TaskAdapter:
    """按参数决定任务是否要求图片；记录每次提交实际拿到的 image（None = 无图提交）。"""

    def __init__(self, need_photo):
        self.need_photo = need_photo
        self.images = []

    def find_active_task(self, session, task_type):
        return {'task': {'id': 42, 'taskName': '07.02查寝签到',
                         'needPhoto': self.need_photo,
                         'startTime': '00:00:00', 'endTime': '23:59:59'}, 'fence': []}

    def submit_checkin(self, session, task_type, task_id, location_str, address,
                       remark, image):
        self.images.append(image)
        return CheckinResult(ok=True, status='success', detail={'rsp': {'code': 0}})


def _run_flow(img_env, monkeypatch, need_photo, image_cfg):
    """跑一次真实 _checkin_flow，返回 (outcome, reason, extra, adapter)。"""
    env = img_env
    acc = BAccount(user_id=env['uid'], account=f'acc_{uuid.uuid4().hex[:8]}', password_enc='x')
    db.session.add(acc)
    db.session.commit()
    adapter = _TaskAdapter(need_photo)
    monkeypatch.setattr(sch, 'get_adapter', lambda: adapter)
    sched = Schedule(user_id=env['uid'], account_id=acc.id, task_type='dorm',
                     mode='standalone', enabled=True)
    outcome, reason, extra = sch._checkin_flow(sched, acc, {'token': 't', 'ua': None},
                                               _cfg(image_cfg), '签到')
    return outcome, reason, extra, adapter


def test_config_off_no_photo_task_submits_without_image(img_env, monkeypatch):
    """配置未启用图库 + 任务不要求图片 → 无图提交，且图库分毫不动。"""
    env = img_env
    ids = _mk_images(env['uid'], 2, group_id=env['gid'])

    outcome, reason, extra, adapter = _run_flow(
        img_env, monkeypatch, False, {'enabled': False, 'strategy': 'recycle', 'groupId': None})

    assert outcome == 'success', reason
    assert adapter.images == [None]                 # 配置没开就不该上传图片
    assert extra.get('image_id') is None
    assert _counts(env['uid']) == (2, 0)            # 配置没开也不该动图库
    assert all(_reload(i).status == 'active' for i in ids)


def test_config_off_photo_required_task_fails(img_env, monkeypatch):
    """配置未启用图库 + 任务要求图片 → 在提交前判失败，并给出可操作的提示。"""
    env = img_env
    _mk_images(env['uid'], 2, group_id=env['gid'])

    outcome, reason, extra, adapter = _run_flow(
        img_env, monkeypatch, True, {'enabled': False, 'strategy': 'recycle', 'groupId': None})

    assert outcome == 'fail'
    assert '启用图库' in reason
    assert adapter.images == []                     # 没走到提交，不交白卷
    assert _counts(env['uid']) == (2, 0)


def test_enabled_but_empty_and_photo_required_fails(img_env, monkeypatch):
    """配置已启用但图库为空 + 任务要求图片 → 仍判失败。"""
    env = img_env                                   # 不建任何图

    outcome, reason, extra, adapter = _run_flow(
        img_env, monkeypatch, True, {'enabled': True, 'strategy': 'recycle',
                                     'groupId': env['gid']})

    assert outcome == 'fail'
    assert '图库暂无可用图片' in reason
    assert adapter.images == []


def test_enabled_empty_but_no_photo_task_degrades_to_no_image(img_env, monkeypatch):
    """配置已启用、图库为空，但任务不要求图片 → 降级为无图提交，不因图库空而失败。

    本次改动的新行为：此前无条件判失败，一个本来不需要图就能签到的任务会被图库拖垮。
    """
    env = img_env                                   # 不建任何图

    outcome, reason, extra, adapter = _run_flow(
        img_env, monkeypatch, False, {'enabled': True, 'strategy': 'recycle',
                                      'groupId': env['gid']})

    assert outcome == 'success', reason
    assert adapter.images == [None]
    assert extra.get('image_id') is None
    assert extra.get('image_group_id') == env['gid']    # 仍记录本次解析出的取图范围


def test_enabled_and_available_image_still_attaches(img_env, monkeypatch):
    """回归：配置启用且有图时，即使任务不要求图片也照样附图（配置项为主）。"""
    env = img_env
    ids = _mk_images(env['uid'], 1, group_id=env['gid'])

    outcome, reason, extra, adapter = _run_flow(
        img_env, monkeypatch, False, {'enabled': True, 'strategy': 'recycle',
                                      'groupId': env['gid']})

    assert outcome == 'success', reason
    assert len(adapter.images) == 1 and adapter.images[0] is not None
    assert adapter.images[0]['bytes'] == IMAGE_BYTES
    assert extra.get('image_id') == ids[0]
    assert _reload(ids[0]).status == 'used'         # recycle 下被占走
