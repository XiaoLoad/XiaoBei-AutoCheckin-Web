# backend/tests/test_image_store.py
import io
import os

import pytest
from PIL import Image

from app.services.image_store import (MAX_IMAGE_PIXELS, MAX_UPLOAD_BYTES,
                                      ImageError, delete_file, normalize_image,
                                      prepare_submit_image, purge_expired_trash,
                                      save_file, user_dir)


def _jpeg(w, h, noise=False):
    im = Image.effect_noise((w, h), 64).convert('RGB') if noise else Image.new('RGB', (w, h), 'red')
    buf = io.BytesIO()
    im.save(buf, format='JPEG', quality=95)
    return buf.getvalue()


def _png_rgba(w=400, h=300):
    im = Image.new('RGBA', (w, h), (255, 0, 0, 128))
    buf = io.BytesIO()
    im.save(buf, format='PNG')
    return buf.getvalue()


def _gif_animated(w=200, h=150, frames=4):
    imgs = [Image.new('RGB', (w, h), (i * 60 % 255, 100, 200)) for i in range(frames)]
    buf = io.BytesIO()
    imgs[0].save(buf, format='GIF', save_all=True, append_images=imgs[1:],
                  duration=120, loop=0)
    return buf.getvalue()


def test_rejects_non_image(app_ctx):
    with pytest.raises(ImageError):
        normalize_image(b'not-an-image-at-all')


def test_rejects_oversized_raw_bytes(app_ctx):
    """超过单文件字节上限的原图在归一化前即被拒绝（不进入 PIL 解码）。"""
    bomb = b'\xff\xd8\xff\xe0' + b'\0' * (MAX_UPLOAD_BYTES + 1)
    with pytest.raises(ImageError) as ei:
        normalize_image(bomb)
    assert '5MB' in str(ei.value)


def test_rejects_decompression_bomb(app_ctx):
    """头部声明超限像素的图片（解压炸弹）必须拒绝，不得进入像素解码。
    构造 PNG 头声明 16000×16000（2.56 亿像素 > 4000×4000 上限）：
    文件体可极小，但 PIL 在 load() 时按声明尺寸分配位图内存——这正是炸弹原理。"""
    import struct
    import zlib

    def _chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    w = h = 16000
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)  # 8bit RGB
    png = (b'\x89PNG\r\n\x1a\n'
           + _chunk(b'IHDR', ihdr)
           + _chunk(b'IDAT', zlib.compress(b'\0' * 64))
           + _chunk(b'IEND', b''))
    assert len(png) < 1024  # 头部合法、体积极小——典型炸弹形态
    with pytest.raises(ImageError) as ei:
        normalize_image(png)
    assert '解压炸弹' in str(ei.value)


def test_bomb_guard_allows_large_but_legitimate_image(app_ctx):
    """防护不误伤：像素恰在上限内的合法图片照常归一化（16000 边以内、4000 边内）。"""
    im = Image.new('RGB', (3999, 3999), 'red')
    buf = io.BytesIO()
    im.save(buf, format='PNG')
    data, w, h, ext, mime = normalize_image(buf.getvalue())
    assert max(w, h) <= 4000  # 下游 1920 收缩前允许通过
    assert ext == '.png'


def test_normalize_small_jpeg_keeps_format_and_size(app_ctx):
    data, w, h, ext, mime = normalize_image(_jpeg(800, 600))
    assert (w, h) == (800, 600)
    assert len(data) <= 180 * 1024
    assert ext == '.jpg' and mime == 'image/jpeg'
    assert data[:2] == b'\xff\xd8'


def test_normalize_big_noise_jpeg_under_180kb_and_max_side(app_ctx):
    data, w, h, ext, mime = normalize_image(_jpeg(2600, 1600, noise=True))
    assert max(w, h) <= 1920
    assert len(data) <= 180 * 1024
    assert mime == 'image/jpeg'
    Image.open(io.BytesIO(data)).verify()


def test_normalize_rejects_gif(app_ctx):
    # 上传端不接受 GIF（B 平台仅支持 JPEG），normalize_image 直接报错
    with pytest.raises(ImageError):
        normalize_image(_gif_animated(200, 150))


def test_normalize_keeps_png_transparency(app_ctx):
    data, w, h, ext, mime = normalize_image(_png_rgba(400, 300))
    assert ext == '.png' and mime == 'image/png'
    p = Image.open(io.BytesIO(data))
    assert p.mode in ('RGBA', 'P')  # 透明通道保留（PNG 无损）


def test_save_delete_roundtrip(app_ctx, tmp_path):
    app_ctx.config['UPLOAD_DIR'] = str(tmp_path)
    fname = save_file(42, _jpeg(100, 100), '.jpg')
    assert fname.endswith('.jpg')
    assert os.path.exists(os.path.join(user_dir(42), fname))
    delete_file(42, '../etc/passwd')        # 路径穿越被 basename 拦截，不抛异常
    delete_file(42, fname)
    assert not os.path.exists(os.path.join(user_dir(42), fname))


def test_save_uses_extension(app_ctx, tmp_path):
    app_ctx.config['UPLOAD_DIR'] = str(tmp_path)
    assert save_file(7, _gif_animated(), '.gif').endswith('.gif')


def test_prepare_submit_converts_all_formats_to_jpeg(app_ctx):
    # B 平台仅接受 JPEG：GIF（含动画）/PNG/JPEG 一律转 JPEG ≤180KB
    cases = [
        (_gif_animated(120, 90), 'image/gif'),
        (_png_rgba(), 'image/png'),
        (_jpeg(2600, 1600, noise=True), 'image/jpeg'),
    ]
    for raw, mime in cases:
        out, omime, oext = prepare_submit_image(raw, mime)
        assert omime == 'image/jpeg' and oext == '.jpg'
        assert out[:2] == b'\xff\xd8'
        assert len(out) <= 180 * 1024
