# 图库蓝图：真实上传（上传即归一化）+ 回收站 + 鉴权文件流。
# 单张 ≤180KB 的成品文件，流式回读开销可忽略；前端 <img> 无法带 Authorization 头，
# 统一走 axios blob 拉取再 URL.createObjectURL 渲染，鉴权姿势与其他接口一致。
import os

from flask import Blueprint, request, send_file

from app.extensions import db
from app.models import PoolImage
from app.models.user import now_cst
from app.services.image_store import (IMAGE_LIMIT, ImageError, delete_file,
                                      normalize_to_jpeg, save_file, user_dir)
from app.utils.auth import token_required
from app.utils.response import error, success

bp = Blueprint('pool_images', __name__, url_prefix='/api/pools')


def _img_dict(i):
    return {'id': i.id, 'name': i.orig_name, 'sizeKb': round((i.size or 0) / 1024),
            'mime': i.mime, 'inTrash': i.status == 'trash'}


def _owned_image(image_id, user):
    return PoolImage.query.filter_by(id=image_id, user_id=user.id).first()


@bp.route('/images', methods=['POST'])
@token_required
def upload_image():
    f = request.files.get('file')
    if not f or not f.filename:
        return error(message='请选择要上传的图片', code=4330, status=400)
    raw = f.read()
    if len(raw) > 5 * 1024 * 1024:
        return error(message='原图不能超过 5MB', code=4331, status=400)
    user = request.current_user
    if PoolImage.query.filter_by(user_id=user.id).count() >= IMAGE_LIMIT:
        return error(message=f'图库最多保存 {IMAGE_LIMIT} 张，请先清理后再上传',
                     code=4332, status=409)
    try:
        jpeg, _, _ = normalize_to_jpeg(raw)
    except ImageError as e:
        return error(message=str(e), code=4333, status=400)
    filename = save_file(user.id, jpeg)
    img = PoolImage(user_id=user.id,
                    orig_name=os.path.basename(f.filename)[:255],
                    filename=filename, size=len(jpeg),
                    mime='image/jpeg', status='active')
    db.session.add(img)
    db.session.commit()
    return success(_img_dict(img), message='上传成功', status=201)


@bp.route('/images/<int:image_id>/trash', methods=['POST'])
@token_required
def trash_image(image_id):
    img = _owned_image(image_id, request.current_user)
    if not img:
        return error(message='图片不存在', code=4040, status=404)
    img.status = 'trash'
    img.trashed_at = now_cst()
    db.session.commit()
    return success(_img_dict(img), message='已移入回收站')


@bp.route('/images/<int:image_id>/restore', methods=['POST'])
@token_required
def restore_image(image_id):
    img = _owned_image(image_id, request.current_user)
    if not img:
        return error(message='图片不存在', code=4040, status=404)
    img.status = 'active'
    img.trashed_at = None
    db.session.commit()
    return success(_img_dict(img), message='已恢复')


@bp.route('/images/<int:image_id>', methods=['DELETE'])
@token_required
def delete_image(image_id):
    img = _owned_image(image_id, request.current_user)
    if not img:
        return error(message='图片不存在', code=4040, status=404)
    delete_file(img.user_id, img.filename)   # 配置体不引用单张图片 id，无引用检查
    db.session.delete(img)
    db.session.commit()
    return success(message='删除成功')


@bp.route('/images/<int:image_id>/file', methods=['GET'])
@token_required
def image_file(image_id):
    img = _owned_image(image_id, request.current_user)
    if not img:
        return error(message='图片不存在', code=4040, status=404)
    path = os.path.join(user_dir(img.user_id), os.path.basename(img.filename))
    if not os.path.exists(path):
        return error(message='图片文件已丢失', code=4334, status=410)
    return send_file(path, mimetype=img.mime or 'image/jpeg')
