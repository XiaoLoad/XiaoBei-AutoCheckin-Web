# 图库蓝图：真实上传（上传即归一化）+ 回收站 + 鉴权文件流。
# 单张 ≤180KB 的成品文件，流式回读开销可忽略；前端 <img> 无法带 Authorization 头，
# 统一走 axios blob 拉取再 URL.createObjectURL 渲染，鉴权姿势与其他接口一致。
import os

from flask import Blueprint, request, send_file

from app.extensions import db
from app.models import ImageGroup, PoolImage
from app.models.user import now_cst
from app.services.image_store import (IMAGE_LIMIT, ImageError, delete_file,
                                      normalize_image, save_file, user_dir)
from app.utils.auth import token_required
from app.utils.response import error, success

bp = Blueprint('pool_images', __name__, url_prefix='/api/pools')

_MAX_GROUP_NAME = 64


def _img_dict(i):
    return {'id': i.id, 'name': i.orig_name, 'sizeKb': round((i.size or 0) / 1024),
            'mime': i.mime, 'groupId': i.group_id,
            'inTrash': i.status == 'trash', 'used': i.status == 'used'}


def _owned_image(image_id, user):
    return PoolImage.query.filter_by(id=image_id, user_id=user.id).first()


def _owned_group(group_id, user):
    return ImageGroup.query.filter_by(id=group_id, user_id=user.id).first()


def _clean_group_name(raw):
    """清洗分组名：去空白、截断到 64 字；空名返回 None"""
    s = str(raw or '').strip()
    return s[:_MAX_GROUP_NAME] if s else None


# ── 图库分组（相册）：用户自建自管，名称通常为寝室号；同寝室账号共用同一分组 ──

@bp.route('/image-groups', methods=['GET'])
@token_required
def list_image_groups():
    user = request.current_user
    groups = ImageGroup.query.filter_by(user_id=user.id).order_by(ImageGroup.id.asc()).all()
    counts = dict(
        db.session.query(PoolImage.group_id, db.func.count(PoolImage.id))
        .filter_by(user_id=user.id, status='active')
        .group_by(PoolImage.group_id).all()
    )
    items = [{'id': g.id, 'name': g.name, 'count': counts.get(g.id, 0)} for g in groups]
    ungrouped = PoolImage.query.filter_by(user_id=user.id, status='active', group_id=None).count()
    return success({'items': items, 'ungrouped': ungrouped})


@bp.route('/image-groups', methods=['POST'])
@token_required
def create_image_group():
    name = _clean_group_name(request.get_json(silent=True).get('name')
                             if request.get_json(silent=True) else None)
    if not name:
        return error(message='请填写分组名称', code=4340, status=400)
    user = request.current_user
    if ImageGroup.query.filter_by(user_id=user.id).count() >= 50:
        return error(message='分组数量已达上限（50 个）', code=4341, status=409)
    g = ImageGroup(user_id=user.id, name=name)
    db.session.add(g)
    db.session.commit()
    return success({'id': g.id, 'name': g.name, 'count': 0}, message='分组已创建', status=201)


@bp.route('/image-groups/<int:group_id>', methods=['PUT'])
@token_required
def rename_image_group(group_id):
    g = _owned_group(group_id, request.current_user)
    if not g:
        return error(message='分组不存在', code=4040, status=404)
    body = request.get_json(silent=True) or {}
    name = _clean_group_name(body.get('name'))
    if not name:
        return error(message='请填写分组名称', code=4340, status=400)
    g.name = name
    db.session.commit()
    return success({'id': g.id, 'name': g.name}, message='分组已重命名')


@bp.route('/image-groups/<int:group_id>', methods=['DELETE'])
@token_required
def delete_image_group(group_id):
    g = _owned_group(group_id, request.current_user)
    if not g:
        return error(message='分组不存在', code=4040, status=404)
    # 组内图片回落到未分组（图片本身不删），引用该分组的配置退化为"全部图库"语义
    PoolImage.query.filter(PoolImage.group_id == g.id).update({'group_id': None})
    db.session.delete(g)
    db.session.commit()
    return success(message='分组已删除，组内图片移至未分组')


@bp.route('/images/<int:image_id>/group', methods=['PUT'])
@token_required
def move_image_group(image_id):
    """移动图片到指定分组；groupId 为 null 表示移至未分组"""
    img = _owned_image(image_id, request.current_user)
    if not img:
        return error(message='图片不存在', code=4040, status=404)
    body = request.get_json(silent=True) or {}
    target = body.get('groupId')
    if target is not None:
        if not isinstance(target, int):
            return error(message='groupId 应为整数或 null', code=4342, status=400)
        if not _owned_group(target, request.current_user):
            return error(message='目标分组不存在', code=4040, status=404)
    img.group_id = target
    db.session.commit()
    return success(_img_dict(img), message='已移动到目标分组')


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
    # 上传目标分组（multipart form 字段 groupId；缺省归未分组）
    group_id = request.form.get('groupId')
    if group_id in (None, '', 'null'):
        group_id = None
    else:
        try:
            group_id = int(group_id)
        except (TypeError, ValueError):
            return error(message='groupId 应为整数', code=4342, status=400)
        if not _owned_group(group_id, user):
            return error(message='所属分组不存在', code=4040, status=404)
    try:
        data, _, _, ext, mime = normalize_image(raw)
    except ImageError as e:
        return error(message=str(e), code=4333, status=400)
    filename = save_file(user.id, data, ext)
    img = PoolImage(user_id=user.id, group_id=group_id,
                    orig_name=os.path.basename(f.filename)[:255],
                    filename=filename, size=len(data),
                    mime=mime, status='active')
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


@bp.route('/images/<int:image_id>/used', methods=['POST'])
@token_required
def mark_image_used(image_id):
    """手动标记为已使用（图库页演示/手动流转）；真实消费由调度器按 config.image.strategy 调 consume_image"""
    img = _owned_image(image_id, request.current_user)
    if not img:
        return error(message='图片不存在', code=4040, status=404)
    img.status = 'used'
    img.trashed_at = None
    db.session.commit()
    return success(_img_dict(img), message='已标记为已使用')


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
