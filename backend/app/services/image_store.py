# 图库文件存储服务：归一化压缩 + 用户分目录落盘 + 回收站扫尾。
# 归一化口径（旧版已验证算法）：长边 ≤1920px；JPEG 质量 80 起每轮 -10，
# 仍超限按 0.7 等比缩放循环，直到 ≤180KB（B 平台提交硬性要求）；
# exif_transpose 顺带矫正方向并剥离 EXIF（含 GPS 的照片不留服务器）。
# 上传即归一化：凌晨定时打卡时零压缩开销，也不会出现「到点压缩失败」的惊喜。
import datetime
import io
import os
import uuid

from flask import current_app
from PIL import Image, ImageOps
from app.models.user import now_cst

MAX_SIDE = 1920
TARGET_KB = 180
IMAGE_LIMIT = 50


class ImageError(ValueError):
    """图片校验或压缩失败（信息直接面向用户展示）"""


def upload_root():
    return current_app.config['UPLOAD_DIR']


def user_dir(user_id):
    d = os.path.join(upload_root(), 'pool_images', str(user_id))
    os.makedirs(d, exist_ok=True)
    return d


def normalize_to_jpeg(raw):
    raw_bytes = bytes(raw or b'')
    try:
        im = Image.open(io.BytesIO(raw_bytes))
        im.load()
    except Exception:
        raise ImageError('文件不是有效图片')
    im = ImageOps.exif_transpose(im).convert('RGB')
    if max(im.size) > MAX_SIDE:
        ratio = MAX_SIDE / max(im.size)
        im = im.resize((max(1, round(im.width * ratio)), max(1, round(im.height * ratio))),
                       Image.LANCZOS)
    quality = 80
    buf = io.BytesIO()
    while True:
        buf = io.BytesIO()
        im.save(buf, format='JPEG', quality=quality, optimize=True)
        if buf.tell() <= TARGET_KB * 1024 or quality <= 10:
            break
        quality -= 10
    while buf.tell() > TARGET_KB * 1024 and min(im.size) > 50:
        im = im.resize((max(1, round(im.width * 0.7)), max(1, round(im.height * 0.7))),
                       Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format='JPEG', quality=quality, optimize=True)
    if buf.tell() > TARGET_KB * 1024:
        raise ImageError('图片无法压缩到 180KB 以内，请更换图片')
    return buf.getvalue(), im.width, im.height


def save_file(user_id, jpeg_bytes):
    fname = uuid.uuid4().hex + '.jpg'
    with open(os.path.join(user_dir(user_id), fname), 'wb') as f:
        f.write(jpeg_bytes)
    return fname


def delete_file(user_id, filename):
    """物理删除单个文件；basename 防路径穿越，缺失静默"""
    path = os.path.join(user_dir(user_id), os.path.basename(filename or ''))
    try:
        os.remove(path)
    except OSError:
        pass


def purge_expired_trash(days=7):
    """物理清除移入回收站超过 days 天的图库记录与文件（应用启动时调用）"""
    from app.extensions import db
    from app.models import PoolImage

    deadline = now_cst() - datetime.timedelta(days=days)
    stale = PoolImage.query.filter(PoolImage.status == 'trash',
                                   PoolImage.trashed_at.isnot(None),
                                   PoolImage.trashed_at < deadline).all()
    for img in stale:
        delete_file(img.user_id, img.filename)
        db.session.delete(img)
    db.session.commit()
    return len(stale)
