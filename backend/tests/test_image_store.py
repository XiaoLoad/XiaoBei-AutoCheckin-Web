# backend/tests/test_image_store.py
import io
import os

import pytest
from PIL import Image

from app.services.image_store import (ImageError, delete_file, normalize_to_jpeg,
                                      purge_expired_trash, save_file, user_dir)


def _jpeg(w, h, noise=False):
    im = Image.effect_noise((w, h), 64).convert('RGB') if noise else Image.new('RGB', (w, h), 'red')
    buf = io.BytesIO()
    im.save(buf, format='JPEG', quality=95)
    return buf.getvalue()


def test_rejects_non_image(app_ctx):
    with pytest.raises(ImageError):
        normalize_to_jpeg(b'not-an-image-at-all')


def test_normalize_small_image_passthrough_size(app_ctx):
    jpeg, w, h = normalize_to_jpeg(_jpeg(800, 600))
    assert w == 800 and h == 600 and len(jpeg) <= 180 * 1024


def test_normalize_big_noise_under_180kb_and_max_side(app_ctx):
    # 高频噪点图极难压缩，验证质量递减 + 缩放循环收敛到 ≤180KB 且长边 ≤1920
    jpeg, w, h = normalize_to_jpeg(_jpeg(2600, 1600, noise=True))
    assert max(w, h) <= 1920
    assert len(jpeg) <= 180 * 1024
    Image.open(io.BytesIO(jpeg)).verify()   # 产物必须是合法 JPEG


def test_save_delete_roundtrip(app_ctx, tmp_path):
    app_ctx.config['UPLOAD_DIR'] = str(tmp_path)
    fname = save_file(42, _jpeg(100, 100))
    assert fname.endswith('.jpg')
    assert os.path.exists(os.path.join(user_dir(42), fname))
    delete_file(42, '../etc/passwd')        # 路径穿越被 basename 拦截，不抛异常
    delete_file(42, fname)
    assert not os.path.exists(os.path.join(user_dir(42), fname))
