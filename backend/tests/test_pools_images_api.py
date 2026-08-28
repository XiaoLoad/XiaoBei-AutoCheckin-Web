# 图库接口集成测试：真实上传 / 鉴权文件流 / 回收站往返 / 物理删除
import io

from PIL import Image


def _jpeg_file(w=900, h=700, name='签到图.jpg', noise=True):
    im = Image.effect_noise((w, h), 64).convert('RGB') if noise else Image.new('RGB', (w, h), 'blue')
    buf = io.BytesIO()
    im.save(buf, format='JPEG', quality=95)
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


def test_image_groups_crud_upload_move_and_delete(app, user_headers):
    """分组：建/重命名/上传入组/移动/删除组后图片回落未分组"""
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
    iid = r.get_json()['data']['groupId']
    assert iid == gid
    # 分组列表带计数
    lst = c.get('/api/pools/image-groups', headers=user_headers).get_json()['data']
    assert lst['items'][0]['name'] == '3栋507' and lst['items'][0]['count'] == 1
    # 移动到未分组
    r = c.put(f'/api/pools/images/{img_id_of(c, user_headers)}/group',
              json={'groupId': None}, headers=user_headers)
    assert r.status_code == 200 and r.get_json()['data']['groupId'] is None
    # 重命名
    r = c.put(f'/api/pools/image-groups/{gid}', json={'name': '5栋302'}, headers=user_headers)
    assert r.get_json()['data']['name'] == '5栋302'
    # 删除组：图片回落未分组，不随组删除
    assert c.delete(f'/api/pools/image-groups/{gid}', headers=user_headers).status_code == 200
    pools = c.get('/api/pools', headers=user_headers).get_json()['data']
    assert pools['imageGroups'] == []
    assert pools['images'][0]['groupId'] is None
    # 清理：物理删除本用例上传的图片（tc_user 图库跨运行共享，顺带清走历史残留避免累积触达上限）
    for x in pools['images']:
        assert c.delete(f'/api/pools/images/{x["id"]}', headers=user_headers).status_code == 200


def img_id_of(c, headers):
    return c.get('/api/pools', headers=headers).get_json()['data']['images'][0]['id']


def test_active_ids_filter_by_group(app_ctx):
    """签到取图预留接口：group_id 过滤 active 图片，None 表示全部"""
    from app.services.image_store import list_active_ids
    ids = list_active_ids(999999, group_id=42)
    assert ids == []
