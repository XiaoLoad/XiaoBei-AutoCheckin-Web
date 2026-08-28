# 图库文件存储服务：归一化压缩 + 用户分目录落盘 + 回收站扫尾。
# 设计口径（对齐旧版 XiaoBeiCheck）：上传时「保留原格式」，仅做尺寸收缩与按格式压缩；
# 提交签到时才按 B 平台口径做格式归一化（见 prepare_submit_image，一律转 JPEG）。
# 上传不接受 GIF（B 平台仅支持 JPEG，动态图也不可提交），故 normalize_image 直接拒绝，
# 其余格式仅做尺寸/体积收敛、保留原格式：
#   - JPEG / WEBP：质量递减直到 ≤180KB；
#   - PNG：无损 optimize（保留透明通道），提交时再转 JPEG；
#   - 其余未知格式（BMP/TIFF 等）兜底转 JPEG。
# exif_transpose 顺带矫正方向并剥离 EXIF（含 GPS 的照片不留服务器）。
import datetime
import io
import os
import random
import uuid

from flask import current_app
from PIL import Image, ImageOps
from app.models.user import now_cst

MAX_SIDE = 1920
TARGET_KB = 180
IMAGE_LIMIT = 50

# 原格式 → (落盘扩展名, MIME)
_FMT_MAP = {
    'JPEG': ('.jpg', 'image/jpeg'),
    'PNG': ('.png', 'image/png'),
    'WEBP': ('.webp', 'image/webp'),
}


class ImageError(ValueError):
    """图片校验或压缩失败（信息直接面向用户展示）"""


def upload_root():
    return current_app.config['UPLOAD_DIR']


def user_dir(user_id):
    d = os.path.join(upload_root(), 'pool_images', str(user_id))
    os.makedirs(d, exist_ok=True)
    return d


def _downscale(im, max_side=MAX_SIDE):
    if max(im.size) <= max_side:
        return im
    ratio = max_side / max(im.size)
    new_size = (max(1, round(im.width * ratio)), max(1, round(im.height * ratio)))
    return im.resize(new_size, Image.LANCZOS)


def _save_jpeg(im, out, target=TARGET_KB):
    out.seek(0)
    out.truncate(0)
    quality = 80
    while True:
        out.seek(0)
        out.truncate(0)
        im.save(out, format='JPEG', quality=quality, optimize=True)
        if out.tell() <= target * 1024 or quality <= 10:
            break
        quality -= 10
    while out.tell() > target * 1024 and min(im.size) > 50:
        im = im.resize((max(1, round(im.width * 0.7)), max(1, round(im.height * 0.7))),
                       Image.LANCZOS)
        out.seek(0)
        out.truncate(0)
        im.save(out, format='JPEG', quality=quality, optimize=True)
    if out.tell() > target * 1024:
        raise ImageError('图片无法压缩到 180KB 以内，请更换图片')


def _save_webp(im, out, target=TARGET_KB):
    out.seek(0)
    out.truncate(0)
    quality = 82
    while True:
        out.seek(0)
        out.truncate(0)
        im.save(out, format='WEBP', quality=quality)
        if out.tell() <= target * 1024 or quality <= 20:
            break
        quality -= 8
    if out.tell() > target * 1024:
        raise ImageError('图片无法压缩到 180KB 以内，请更换图片')


def _save_png(im, out):
    # 无损 optimize；PNG 体积受内容限制，不强制 ≤180KB（提交时再转 JPEG）
    out.seek(0)
    out.truncate(0)
    im.save(out, format='PNG', optimize=True)


def normalize_image(raw):
    """上传归一化：保留原格式（不强制转 JPEG），仅做尺寸收缩与按格式压缩。
    返回 (bytes, width, height, ext, mime)：
      - JPEG / WEBP：质量递减直到 ≤180KB；
      - PNG：无损 optimize（透明通道保留）；
      - 其它未知格式：兜底转 JPEG。
    GIF 不被接受（B 平台仅支持 JPEG），直接报错。"""
    raw_bytes = bytes(raw or b'')
    try:
        im = Image.open(io.BytesIO(raw_bytes))
        im.load()
    except Exception:
        raise ImageError('文件不是有效图片')
    fmt = (im.format or '').upper()
    if fmt == 'GIF':
        raise ImageError('不支持 GIF 格式，请上传 JPG / PNG / WEBP')

    # 转置（矫正方向）+ 收缩，按格式压缩
    im = ImageOps.exif_transpose(im)
    im = _downscale(im)
    ext, mime = _FMT_MAP.get(fmt, ('.jpg', 'image/jpeg'))

    out = io.BytesIO()
    if fmt == 'JPEG':
        _save_jpeg(im, out)
    elif fmt == 'WEBP':
        _save_webp(im, out)
    elif fmt == 'PNG':
        _save_png(im, out)
    else:
        im = im.convert('RGB')
        _save_jpeg(im, out)
        ext, mime = '.jpg', 'image/jpeg'

    data = out.getvalue()
    w, h = im.size
    return data, w, h, ext, mime


def prepare_submit_image(raw_bytes, mime):
    """提交签到前的格式归一化（Module E 真实提交时调用）：B 平台仅接受 JPEG，
    故无论原始格式（PNG/WEBP/JPEG/未知均含）一律转 JPEG ≤180KB。
    对应「上传保留原格式、提交时统一转 JPEG」的口径；GIF 已在上传端拒绝，不会到达此处。"""
    try:
        im = Image.open(io.BytesIO(bytes(raw_bytes or b'')))
        im.load()
    except Exception:
        raise ImageError('图片无法解析，无法提交')
    im = ImageOps.exif_transpose(im).convert('RGB')
    im = _downscale(im)
    out = io.BytesIO()
    _save_jpeg(im, out)
    return out.getvalue(), 'image/jpeg', '.jpg'


def save_file(user_id, img_bytes, ext='.jpg'):
    fname = uuid.uuid4().hex + ext
    with open(os.path.join(user_dir(user_id), fname), 'wb') as f:
        f.write(img_bytes)
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


def list_active_ids(user_id, group_id=None):
    """签到取图预留：按用户（可选按分组）取 active 图片 id 列表（新→旧）。
    签到图片提交链路落地时，配置 image.groupId 即按此过滤取图；
    group_id 为 None 表示不分组过滤（全部图库）。"""
    from app.models import PoolImage

    q = PoolImage.query.filter_by(user_id=user_id, status='active')
    if group_id is not None:
        q = q.filter_by(group_id=group_id)
    return [i.id for i in q.order_by(PoolImage.id.desc()).all()]


def consume_image(image_id, user_id, strategy):
    """消费图片流转（供调度器在真实签到提交时按 config.image.strategy 调用）。
    recycle 循环复用 → used（保留、不入回收站、不受 7 天清理影响，可轮回取用）；
    trash 用后入回收站 → trash（可 7 天内恢复）；
    delete 用后删除 → 物理删除文件与记录；
    缺省/未知策略 → trash（可恢复，避免误删）。

    关键：recycle 不再走 trash，从而与回收站 7 天自动删除解耦，解决「轮回使用却被清理」的冲突。"""
    from app.extensions import db
    from app.models import PoolImage

    img = PoolImage.query.filter_by(id=image_id, user_id=user_id).first()
    if not img:
        return None
    if strategy == 'recycle':
        img.status = 'used'
        img.trashed_at = None
    elif strategy == 'delete':
        delete_file(img.user_id, img.filename)
        db.session.delete(img)
    else:  # 'trash' 或未知：落回收站，沿用原可恢复语义
        img.status = 'trash'
        img.trashed_at = now_cst()
    db.session.commit()
    return img


def consume_next_image(user_id, group_id=None, strategy='trash'):
    """按取图范围随机消费一张图片（并发安全，供调度器打卡成功后调用）。

    范围：group_id None=全部图库，否则限定分组（对齐 config.image.groupId 的 '' 口径）。
    随机性：对范围内 active 图片 id 洗牌后逐一尝试。
    防冲突：用「原子 UPDATE ... WHERE status='active'」抢占，命中 rowcount==1 才算消费成功；
    多账号同分钟并发随机到同一张时，只有一个任务命中，其余自动改试下一张，无需显式加锁。
    策略：recycle → used（轮回复用）；trash → 回收站；delete → 物理删除；未知 → trash。
    recycle 轮回语义：范围内 active 取尽后，将范围内 used 整批放回 active（转入已使用的图片
    重新可用），再取一轮；trash/delete 池空即无图可消费，不回池。

    返回被消费图片的 id；范围内无可用图片返回 None。"""
    from sqlalchemy import delete as sa_delete
    from sqlalchemy import update

    from app.extensions import db
    from app.models import PoolImage

    def _active_ids():
        q = db.session.query(PoolImage.id).filter(
            PoolImage.user_id == user_id, PoolImage.status == 'active')
        if group_id is not None:
            q = q.filter(PoolImage.group_id == group_id)
        return [r.id for r in q.all()]

    def _try_consume_once():
        ids = _active_ids()
        random.shuffle(ids)
        for img_id in ids:
            occupy = [PoolImage.id == img_id, PoolImage.status == 'active']
            if strategy == 'delete':
                row = db.session.get(PoolImage, img_id)
                if row is None:
                    continue
                filename = row.filename  # 先取文件名，commit 后对象过期无法再惰性读取
                res = db.session.execute(
                    sa_delete(PoolImage).where(*occupy)
                    .execution_options(synchronize_session=False))
                db.session.commit()
                if res.rowcount == 1:
                    delete_file(user_id, filename)
                    return img_id
            else:
                recycle = strategy == 'recycle'
                res = db.session.execute(
                    update(PoolImage).where(*occupy)
                    .values(status='used' if recycle else 'trash',
                            trashed_at=None if recycle else now_cst())
                    .execution_options(synchronize_session=False))
                db.session.commit()
                if res.rowcount == 1:
                    return img_id
        return None

    consumed = _try_consume_once()
    if consumed is not None:
        return consumed
    if strategy != 'recycle':
        return None

    # recycle 回池：范围内 used 整批放回 active（used→active 幂等，并发重复回池无害）
    reclaim = [PoolImage.user_id == user_id, PoolImage.status == 'used']
    if group_id is not None:
        reclaim.append(PoolImage.group_id == group_id)
    res = db.session.execute(
        update(PoolImage).where(*reclaim)
        .values(status='active', trashed_at=None)
        .execution_options(synchronize_session=False))
    db.session.commit()
    if res.rowcount == 0:
        return None
    return _try_consume_once()
