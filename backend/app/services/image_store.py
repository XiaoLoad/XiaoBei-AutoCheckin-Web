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
# 上传原图字节上限（与路由层 multipart 校验同源；MAX_CONTENT_LENGTH 8MB 是请求体总上限，
# 此处是单文件业务上限——路由先按 Content-Length / 流式读取拒绝超大文件，此处兜底双保险）
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# 解压炸弹防护：PIL 默认 ~1.79 亿像素才报错（且 0.89 亿仅告警），一张几 MB 的 PNG 可
# 解码成数百 MB 位图。本系统提交端最大 1920 边（约 369 万像素），放宽到 4 倍余量；
# 超限直接拒绝，不给「告警后继续解码」留空间。
MAX_IMAGE_PIXELS = 4000 * 4000

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


def _open_image(raw_bytes):
    """按防护口径打开图片：像素上限收紧 + 解压炸弹异常转 ImageError。
    Image.open 只读头部（不解码像素），随后 im.load() 才真正分配位图内存——
    像素上限在 load() 前生效，头部声明超限的文件根本不会进入解码。"""
    from PIL import ImageFile

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        im = Image.open(io.BytesIO(bytes(raw_bytes or b'')))
        im.load()
    except Image.DecompressionBombError:
        raise ImageError('图片尺寸过大（疑似解压炸弹），已拒绝')
    except Exception:
        raise ImageError('文件不是有效图片')
    # 截断式损坏图片（声明尺寸与实际数据不符）默认会在 load() 抛 OSError，
    # 但容错截断模式（LOAD_TRUNCATED_IMAGES）被其他库打开时可能静默产出残图，
    # 这里显式关闭容错，保证「不是有效图片」的判定不被环境变量放大
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    return im


def normalize_image(raw):
    """上传归一化：保留原格式（不强制转 JPEG），仅做尺寸收缩与按格式压缩。
    返回 (bytes, width, height, ext, mime)：
      - JPEG / WEBP：质量递减直到 ≤180KB；
      - PNG：无损 optimize（透明通道保留）；
      - 其它未知格式：兜底转 JPEG。
    GIF 不被接受（B 平台仅支持 JPEG），直接报错。"""
    raw_bytes = bytes(raw or b'')
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise ImageError('原图不能超过 5MB')
    im = _open_image(raw_bytes)
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
    对应「上传保留原格式、提交时统一转 JPEG」的口径；GIF 已在上传端拒绝，不会到达此处。
    数据来源为已归一化的自存文件，仍走同一 _open_image 防护（防库内容被外部篡改）。"""
    im = _open_image(raw_bytes)
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


def _reclaim_used(user_id, group_id=None):
    """recycle 回池：把取图范围内的 used 整批放回 active，返回回池张数。

    「已使用」只是「本轮内别重复用同一张」的暂存态，不是终态：范围内 active 取尽即整批
    回池、重新随机，图确实不够时才必然重复。本函数是**唯一的回池出口**——历史上认领链路
    漏接了它（接了回池的是另一条已废弃的消费链路），于是签到取不到图直接判失败、第 5 人起
    全部报「图库暂无可用图片」，而 UI 一直承诺「用完放回图库，之后仍会被抽中」。"""
    from sqlalchemy import update
    from app.extensions import db
    from app.models import PoolImage

    cond = [PoolImage.user_id == user_id, PoolImage.status == 'used']
    if group_id is not None:
        cond.append(PoolImage.group_id == group_id)
    res = db.session.execute(
        update(PoolImage).where(*cond)
        .values(status='active', trashed_at=None)
        .execution_options(synchronize_session=False))
    db.session.commit()
    return res.rowcount


def _claim_once(user_id, group_id=None, strategy='trash'):
    """单轮认领：只从 active 里挑，不涉及回池（回池由 claim_image_for_submit 兜底）。"""
    from app.extensions import db
    from app.models import PoolImage
    from sqlalchemy import delete as sa_delete
    from sqlalchemy import update

    for _ in range(5):  # 认领冲突（并发抢占失败）最多换 5 张
        q = db.session.query(PoolImage).filter(
            PoolImage.user_id == user_id, PoolImage.status == 'active')
        if group_id is not None:
            q = q.filter(PoolImage.group_id == group_id)
        candidates = q.order_by(PoolImage.id.desc()).all()
        if not candidates:
            return None
        img = random.choice(candidates)
        path = os.path.join(user_dir(user_id), os.path.basename(img.filename))
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except OSError:
            # 文件丢失：跳过该图，下一轮重选（候选里仍有其它图时）
            continue

        occupy = [PoolImage.id == img.id, PoolImage.user_id == user_id,
                  PoolImage.status == 'active']
        if strategy == 'delete':
            row = db.session.get(PoolImage, img.id)
            filename = row.filename
            # commit 后对象过期，且该行已被删除、惰性刷新必然失败（ObjectDeletedError），
            # 故全部字段须在 commit 前取出。
            img_id, orig_name, mime = row.id, row.orig_name, row.mime
            res = db.session.execute(
                sa_delete(PoolImage).where(*occupy).execution_options(synchronize_session=False))
            db.session.commit()
            if res.rowcount == 1:
                delete_file(user_id, filename)
                return {'id': img_id, 'bytes': data,
                        'orig_name': orig_name, 'mime': mime}
        else:
            recycle = strategy == 'recycle'
            res = db.session.execute(
                update(PoolImage).where(*occupy)
                .values(status='used' if recycle else 'trash',
                        trashed_at=None if recycle else now_cst())
                .execution_options(synchronize_session=False))
            db.session.commit()
            if res.rowcount == 1:
                return {'id': img.id, 'bytes': data,
                        'orig_name': img.orig_name, 'mime': img.mime}
    return None


def claim_image_for_submit(user_id, group_id=None, strategy='trash'):
    """提交签到链路的图片认领（**全系统唯一的取图实现**）：随机选一张 active 图 → 读出字节 →
    按策略原子认领。字节与认领严格对应（读文件后按 id 认领，认领失败换一张重试），
    供调度器在提交前取图、失败后回滚。返回 {'id', 'bytes', 'orig_name', 'mime'}；无可用图返回 None。

    认领语义：recycle → used（轮回复用）；trash → 回收站；delete → 删除记录与文件
    （字节已先读出，供提交使用）。strategy 未知按 trash。

    recycle 轮回：active 取尽即把范围内 used 整批回池再取一轮（见 _reclaim_used）；
    只有回池无图可回（图确实用完了）才判无图。演示 4 张图供 6 人签到由此成立——
    前 4 人各用一张不同的，后 2 人从回池的 4 张里随机复用。"""
    claimed = _claim_once(user_id, group_id, strategy)
    if claimed is not None or strategy != 'recycle':
        return claimed
    if _reclaim_used(user_id, group_id) == 0:
        return None
    return _claim_once(user_id, group_id, strategy)


def rollback_claim(image_id, user_id, strategy):
    """提交失败时回滚认领：recycle/trash → 恢复 active（幂等）；delete 不回滚
    （记录与文件已物理删除，仅由调用方记日志）。"""
    if strategy == 'delete':
        return False
    from app.extensions import db
    from app.models import PoolImage
    from sqlalchemy import update

    res = db.session.execute(
        update(PoolImage)
        .where(PoolImage.id == image_id, PoolImage.user_id == user_id,
               PoolImage.status.in_(['used', 'trash']))
        .values(status='active', trashed_at=None)
        .execution_options(synchronize_session=False))
    db.session.commit()
    return res.rowcount == 1
