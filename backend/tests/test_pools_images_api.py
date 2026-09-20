# 图库接口集成测试：真实上传 / 鉴权文件流 / 回收站往返 / 物理删除
import io

from PIL import Image


def _jpeg_file(w=900, h=700, name='签到图.jpg', noise=True):
    im = Image.effect_noise((w, h), 64).convert('RGB') if noise else Image.new('RGB', (w, h), 'blue')
    buf = io.BytesIO()
    im.save(buf, format='JPEG', quality=95)
    buf.seek(0)
    return {'file': (buf, name)}


def _gif_file(name='动画.gif', frames=4):
    imgs = [Image.new('RGB', (200, 150), (i * 60 % 255, 100, 200)) for i in range(frames)]
    buf = io.BytesIO()
    imgs[0].save(buf, format='GIF', save_all=True, append_images=imgs[1:], duration=120, loop=0)
    buf.seek(0)
    return {'file': (buf, name)}


def test_upload_list_trash_restore_delete(app, user_headers):
    c = app.test_client()
    r = c.post('/api/pools/images', data=_jpeg_file(), headers=user_headers,
               content_type='multipart/form-data')
    assert r.status_code == 201
    img = r.get_json()['data']
    assert img['name'] == '签到图.jpg' and img['inTrash'] is False
    assert 0 < img['sizeKb'] <= 180
    assert img['mime'] == 'image/jpeg'
    iid = img['id']

    # 文件流：本人可读，无 token 401
    assert c.get(f'/api/pools/images/{iid}/file').status_code == 401
    assert c.get(f'/api/pools/images/{iid}/file',
                 headers=user_headers).status_code == 200
    assert c.get(f'/api/pools/images/{iid}/file',
                 headers=user_headers).data[:2] == b'\xff\xd8'

    # 回收站往返
    assert c.post(f'/api/pools/images/{iid}/trash', headers=user_headers).status_code == 200
    assert c.get('/api/pools', headers=user_headers).get_json()['data']['images'][0]['inTrash'] is True
    assert c.post(f'/api/pools/images/{iid}/restore', headers=user_headers).status_code == 200
    # 删除（物理）；tc_user 图库跨用例/跨运行共享，只断言本用例的图已不存在
    assert c.delete(f'/api/pools/images/{iid}', headers=user_headers).status_code == 200
    remain = c.get('/api/pools', headers=user_headers).get_json()['data']['images']
    assert all(x['id'] != iid for x in remain)


def test_upload_rejects_non_image_and_404_after_delete(app, user_headers):
    c = app.test_client()
    r = c.post('/api/pools/images', data={'file': (io.BytesIO(b'junk'), 'x.png')},
               headers=user_headers, content_type='multipart/form-data')
    assert r.status_code == 400


def test_upload_rejects_gif(app, user_headers):
    """上传端不接受 GIF：返回 400 且不在图库落库"""
    c = app.test_client()
    r = c.post('/api/pools/images', data=_gif_file(), headers=user_headers,
               content_type='multipart/form-data')
    assert r.status_code == 400, r.get_json()
    # 图库不新增任何 GIF（tc_user 图库跨运行共享，仅断言本用例未落库）
    remain = c.get('/api/pools', headers=user_headers).get_json()['data']['images']
    assert all(not i['name'].endswith('.gif') for i in remain)


def test_image_groups_crud_upload_move_and_delete(app, user_headers):
    """分组：建/重命名/上传入组/移动/删除组后图片回落未分组

    断言一律自指（按本用例的 gid / 图片 id 取），不假设 tc_user 名下只有本用例的数据——
    tc_user 跨用例、跨运行共享，同文件里还有别的建组/传图用例，用 `items[0]` 或
    `imageGroups == []` 会被任何残留顶掉，且一次失败会连累后续所有运行。
    """
    c = app.test_client()
    # 建组
    r = c.post('/api/pools/image-groups', json={'name': '3栋507'}, headers=user_headers)
    assert r.status_code == 201, r.get_json()
    gid = r.get_json()['data']['id']
    # 空名被拒
    assert c.post('/api/pools/image-groups', json={'name': '  '},
                  headers=user_headers).status_code == 400
    # 上传入组
    r = c.post('/api/pools/images', data={**_jpeg_file(), 'groupId': str(gid)},
               headers=user_headers, content_type='multipart/form-data')
    assert r.status_code == 201, r.get_json()
    img = r.get_json()['data']
    assert img['groupId'] == gid
    # 分组列表带计数
    lst = c.get('/api/pools/image-groups', headers=user_headers).get_json()['data']
    mine = next(g for g in lst['items'] if g['id'] == gid)
    assert mine['name'] == '3栋507' and mine['count'] == 1
    # 移动到未分组
    r = c.put(f'/api/pools/images/{img["id"]}/group',
              json={'groupId': None}, headers=user_headers)
    assert r.status_code == 200 and r.get_json()['data']['groupId'] is None
    # 重命名
    r = c.put(f'/api/pools/image-groups/{gid}', json={'name': '5栋302'}, headers=user_headers)
    assert r.get_json()['data']['name'] == '5栋302'
    # 删除组：图片回落未分组，不随组删除
    assert c.delete(f'/api/pools/image-groups/{gid}', headers=user_headers).status_code == 200
    pools = c.get('/api/pools', headers=user_headers).get_json()['data']
    assert gid not in [g['id'] for g in pools['imageGroups']]
    assert next(x for x in pools['images'] if x['id'] == img['id'])['groupId'] is None
    # 清理：物理删除本用例上传的图片（tc_user 图库跨运行共享，顺带清走历史残留避免累积触达上限）
    for x in pools['images']:
        assert c.delete(f'/api/pools/images/{x["id"]}', headers=user_headers).status_code == 200


def test_image_group_counts_split_active_and_used(app, user_headers):
    """分组及未分组的张数分两档返回：count=active / usedCount=used。

    为何分两档：同一图库可被不同策略的配置套引用——recycle 下 active 取尽会把 used 整批
    回池（「可抽」= count + usedCount），trash/delete 只算 count。资源接口不知道调用方问的
    是哪个配置套，故只给原始计数，策略由调用方换算。已使用的图若混进 count，trash/delete
    策略下就会虚报可抽数。
    """
    c = app.test_client()

    def groups():
        return c.get('/api/pools/image-groups', headers=user_headers).get_json()['data']

    # 自愈：清掉本用例上次中断留下的分组（tc_ 前缀是项目测试数据的约定）
    for g in [x for x in groups()['items'] if x['name'].startswith('tc_usedcount')]:
        _purge_group(c, user_headers, g['id'])

    base = groups()
    base_ungrouped, base_ungrouped_used = base['ungrouped'], base['ungroupedUsed']

    # 建独立分组，避免与 tc_user 图库里的历史残留互相干扰
    gid = c.post('/api/pools/image-groups', json={'name': 'tc_usedcount'},
                 headers=user_headers).get_json()['data']['id']
    ids = []
    try:
        for _ in range(2):
            r = c.post('/api/pools/images', data={**_jpeg_file(), 'groupId': str(gid)},
                       headers=user_headers, content_type='multipart/form-data')
            assert r.status_code == 201, r.get_json()
            ids.append(r.get_json()['data']['id'])

        def bucket():
            data = groups()
            return next(g for g in data['items'] if g['id'] == gid), data

        g, _ = bucket()
        assert (g['count'], g['usedCount']) == (2, 0)

        # 标记已使用：总数守恒，只是从 active 挪到 used
        assert c.post(f'/api/pools/images/{ids[0]}/used',
                      headers=user_headers).status_code == 200
        g, _ = bucket()
        assert (g['count'], g['usedCount']) == (1, 1)

        # 恢复回 active
        assert c.post(f'/api/pools/images/{ids[0]}/restore',
                      headers=user_headers).status_code == 200
        g, _ = bucket()
        assert (g['count'], g['usedCount']) == (2, 0)

        # 未分组同样分两档：移出一张并标记已使用，组内两档同步递减、未分组 used 加一
        assert c.put(f'/api/pools/images/{ids[1]}/group', json={'groupId': None},
                     headers=user_headers).status_code == 200
        assert c.post(f'/api/pools/images/{ids[1]}/used',
                      headers=user_headers).status_code == 200
        g, data = bucket()
        assert (g['count'], g['usedCount']) == (1, 0)
        assert data['ungrouped'] == base_ungrouped
        assert data['ungroupedUsed'] == base_ungrouped_used + 1
    finally:
        # tc_user 图库跨用例/跨运行共享，本用例自建的数据必须清干净；
        # 断言删除结果，避免清理静默失败后残留污染后续用例（曾因 items[0] 被顶掉而连带失败）
        for iid in ids:
            # 其中一张已被移到未分组，故按 id 删而非靠 _purge_group 扫描组内
            c.delete(f'/api/pools/images/{iid}', headers=user_headers)
        _purge_group(c, user_headers, gid)
        assert all(x['id'] != gid for x in groups()['items']), '用例残留分组未清干净'


def _purge_group(c, user_headers, gid):
    """删除分组前先物理删掉组内图片（分组删掉后图片会回落未分组，更难清理）"""
    imgs = c.get('/api/pools', headers=user_headers).get_json()['data']['images']
    for x in imgs:
        if str(x.get('groupId')) == str(gid):
            assert c.delete(f'/api/pools/images/{x["id"]}',
                            headers=user_headers).status_code == 200
    assert c.delete(f'/api/pools/image-groups/{gid}',
                    headers=user_headers).status_code == 200
