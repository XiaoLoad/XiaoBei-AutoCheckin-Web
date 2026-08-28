# backend/tests/test_consume_next_image.py
# 图库消费（调度器打卡成功后调用）：随机取图、按策略流转、recycle 轮回回池、并发防冲突。
# 消费走原生 UPDATE（synchronize_session=False），断言前一律 expire_all 重读，避免 ORM 缓存脏读。
import uuid

import pytest

from app.extensions import db
from app.models import PoolImage
from app.models.user import User
from app.services.image_store import consume_next_image


def _mk_user():
    u = User(username=f'tc_img_{uuid.uuid4().hex[:10]}', role='user',
             enabled=True, quota=100, used_quota=0)
    u.set_password('pw-' + u.username)
    db.session.add(u)
    db.session.commit()
    return u


def _mk_images(user_id, n, group_id=None, status='active'):
    rows = []
    for i in range(n):
        img = PoolImage(user_id=user_id, group_id=group_id, orig_name=f'p{i}.jpg',
                        filename=f'f{i}_{uuid.uuid4().hex[:6]}.jpg', size=1024,
                        mime='image/jpeg', status=status)
        db.session.add(img)
        rows.append(img)
    db.session.commit()
    return sorted(r.id for r in rows)


def _reload(img_id):
    db.session.expire_all()
    return db.session.get(PoolImage, img_id)


def test_recycle_consumes_each_image_once(app_ctx):
    """轮回：逐张取用互不重复，取尽后全部处于 used（保留不删）。"""
    u = _mk_user()
    ids = _mk_images(u.id, 3)

    consumed = [consume_next_image(u.id, None, 'recycle') for _ in range(3)]

    assert sorted(consumed) == ids
    assert all(_reload(i).status == 'used' for i in ids)
    assert all(_reload(i).trashed_at is None for i in ids)  # recycle 不落回收站


def test_recycle_reclaims_used_when_pool_empty(app_ctx):
    """轮回核心：图库用尽后，已使用图片整批放回图库再继续取用。"""
    u = _mk_user()
    ids = _mk_images(u.id, 3)
    for _ in range(3):
        consume_next_image(u.id, None, 'recycle')

    again = consume_next_image(u.id, None, 'recycle')

    assert again in ids
    assert _reload(again).status == 'used'          # 本次取用的又转入已使用
    remained = [i for i in ids if _reload(i).status == 'active']
    assert len(remained) == 2                        # 其余回到图库等待下一轮


def test_trash_strategy_does_not_reclaim(app_ctx):
    """回收站策略：取用后落回收站并记录时刻；池空即为无图，不做回池。"""
    u = _mk_user()
    ids = _mk_images(u.id, 2)

    first = consume_next_image(u.id, None, 'trash')
    assert first in ids
    assert _reload(first).status == 'trash'
    assert _reload(first).trashed_at is not None

    assert consume_next_image(u.id, None, 'trash') in ids
    assert consume_next_image(u.id, None, 'trash') is None


def test_delete_strategy_removes_record(app_ctx):
    """删除策略：取用即物理删除记录与文件；池空即为无图。"""
    u = _mk_user()
    ids = _mk_images(u.id, 2)

    first = consume_next_image(u.id, None, 'delete')
    assert first in ids
    assert _reload(first) is None

    assert consume_next_image(u.id, None, 'delete') in ids
    assert consume_next_image(u.id, None, 'delete') is None


def test_group_scope_limits_selection(app_ctx):
    """取图范围：限定分组时只消费该分组图片，分组外不受影响。
    recycle 轮回特性下，组内用尽会整批回池再取，仍只取组内、绝不波及分组外。"""
    u = _mk_user()
    from app.models.pools import ImageGroup
    g = ImageGroup(user_id=u.id, name=f'g{uuid.uuid4().hex[:6]}')
    db.session.add(g)
    db.session.commit()

    in_group = _mk_images(u.id, 2, group_id=g.id)
    outside = _mk_images(u.id, 1)

    consumed = [consume_next_image(u.id, g.id, 'recycle') for _ in range(2)]
    assert sorted(consumed) == in_group
    assert _reload(outside[0]).status == 'active'          # 分组外原样保留

    # 组内用尽后整批回池复用，仍只取组内、不波及分组外
    recycled = consume_next_image(u.id, g.id, 'recycle')
    assert recycled in in_group
    assert _reload(recycled).status == 'used'
    assert _reload(outside[0]).status == 'active'          # 分组外始终不受影响


def test_concurrent_pick_never_reuses_same_image(app_ctx, monkeypatch):
    """并发防冲突：两个任务随机到同一张时，后到者抢占失败自动改试下一张。

    固定 shuffle 为升序，构造「两个任务选中同一张」的最坏情况：
    第一个命中，第二个因 WHERE status='active' 已不命中而转向下一张。
    """
    monkeypatch.setattr('random.shuffle', lambda lst: lst.sort())
    u = _mk_user()
    ids = _mk_images(u.id, 3)

    first = consume_next_image(u.id, None, 'recycle')
    second = consume_next_image(u.id, None, 'recycle')

    assert first == ids[0]
    assert second == ids[1]
    assert _reload(first).status == 'used'
    assert _reload(second).status == 'used'
    assert _reload(ids[2]).status == 'active'
