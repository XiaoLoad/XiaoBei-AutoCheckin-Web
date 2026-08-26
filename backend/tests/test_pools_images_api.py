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
    # 删除（物理）
    assert c.delete(f'/api/pools/images/{iid}', headers=user_headers).status_code == 200
    assert c.get('/api/pools', headers=user_headers).get_json()['data']['images'] == []


def test_upload_rejects_non_image_and_404_after_delete(app, user_headers):
    c = app.test_client()
    r = c.post('/api/pools/images', data={'file': (io.BytesIO(b'junk'), 'x.png')},
               headers=user_headers, content_type='multipart/form-data')
    assert r.status_code == 400
