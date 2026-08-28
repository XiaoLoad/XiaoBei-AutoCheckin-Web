# 平台资源池蓝图：四池聚合读取 + 位置池 CRUD。
# 可见性口径：is_system=1 全员可读、仅 admin 可写；私有行严格 user_id 隔离。
import json

from flask import Blueprint, request

from app.extensions import db
from app.models import (ConfigSet, ImageGroup, PoolCredential, PoolImage,
                        PoolLocation, PoolUa)
from app.schemas.pools_schema import (load_credential, load_credential_update,
                                      load_location, load_ua,
                                      mask_fields, required_missing)
from app.services.crypto import decrypt, encrypt
from app.utils.auth import admin_required, token_required
from app.utils.response import error, success

bp = Blueprint('pools', __name__, url_prefix='/api/pools')


@bp.route('', methods=['GET'])
@token_required
def aggregate():
    """四池一次拉齐：locations（系统+本人）、uas（系统+本人）、credentials/images（严格本人）"""
    user = request.current_user
    locs = (PoolLocation.query
            .filter(db.or_(PoolLocation.is_system.is_(True), PoolLocation.user_id == user.id))
            .order_by(PoolLocation.is_system.desc(), PoolLocation.id.asc()).all())
    uas = (PoolUa.query
           .filter(db.or_(PoolUa.is_system.is_(True), PoolUa.user_id == user.id))
           .order_by(PoolUa.id.asc()).all())
    creds = (PoolCredential.query.filter_by(user_id=user.id)
             .order_by(PoolCredential.id.asc()).all())
    imgs = (PoolImage.query.filter_by(user_id=user.id)
            .order_by(PoolImage.id.desc()).all())
    groups = (ImageGroup.query.filter_by(user_id=user.id)
              .order_by(ImageGroup.id.asc()).all())

    def cred_dict(c):
        try:
            fields = json.loads(decrypt(c.secret_enc))
        except Exception:
            fields = {}
        return {'id': c.id, 'channel': c.channel, 'name': c.name,
                'fields': mask_fields(fields), 'enabled': bool(c.enabled)}

    return success({
        'locations': [l.to_dict() for l in locs],
        'images': [{'id': i.id, 'name': i.orig_name,
                    'sizeKb': round((i.size or 0) / 1024), 'mime': i.mime,
                    'groupId': i.group_id,
                    'inTrash': i.status == 'trash'} for i in imgs],
        'imageGroups': [{'id': g.id, 'name': g.name} for g in groups],
        'credentials': [cred_dict(c) for c in creds],
        'uas': [u.to_dict() for u in uas],
    })


def _visible_location(loc_id, user):
    loc = db.session.get(PoolLocation, loc_id)
    if not loc or (not loc.is_system and loc.user_id != user.id):
        return None
    return loc


def _system_guard(loc, user):
    """系统行的写操作仅 admin；返回 err_resp 或 None"""
    if loc.is_system and user.role != 'admin':
        return error(message='平台预设位置仅管理员可维护', code=4302, status=403)
    return None


@bp.route('/locations', methods=['POST'])
@token_required
def create_location():
    payload = request.get_json(silent=True) or {}
    ok, data, msg, code = load_location(payload)
    if not ok:
        return error(message=msg, code=code, status=400)
    is_system = payload.get('scope') == 'system'
    if is_system and request.current_user.role != 'admin':
        return error(message='平台预设位置仅管理员可维护', code=4302, status=403)
    loc = PoolLocation(user_id=request.current_user.id, is_system=is_system, **data)
    db.session.add(loc)
    db.session.commit()
    return success(loc.to_dict(), message='添加成功', status=201)


@bp.route('/locations/<int:loc_id>', methods=['PUT'])
@token_required
def update_location(loc_id):
    user = request.current_user
    loc = _visible_location(loc_id, user)
    if not loc:
        return error(message='位置不存在', code=4040, status=404)
    guard = _system_guard(loc, user)
    if guard:
        return guard
    payload = request.get_json(silent=True) or {}
    ok, data, msg, code = load_location(payload)
    if not ok:
        return error(message=msg, code=code, status=400)
    for k, v in data.items():
        setattr(loc, k, v)
    db.session.commit()
    return success(loc.to_dict(), message='保存成功')


@bp.route('/locations/<int:loc_id>', methods=['DELETE'])
@token_required
def delete_location(loc_id):
    user = request.current_user
    loc = _visible_location(loc_id, user)
    if not loc:
        return error(message='位置不存在', code=4040, status=404)
    guard = _system_guard(loc, user)
    if guard:
        return guard
    refs = ConfigSet.query.filter(ConfigSet.location_id == loc.id).count()
    if refs:
        return error(message=f'该位置被 {refs} 个配置套引用，无法删除',
                     code=4303, data={'refs': refs}, status=409)
    db.session.delete(loc)
    db.session.commit()
    return success(message='删除成功')


# ---------------- UA 模板池（平台级资源，仅管理员维护） ----------------

def _ua_ref_count(ua_id):
    """扫描配置体 advanced.uaTemplateId 引用计数（数据量小，Python 扫描足够）"""
    cnt = 0
    for cs in ConfigSet.query.all():
        adv = (cs.config or {}).get('advanced') or {}
        if adv.get('uaTemplateId') == ua_id:
            cnt += 1
    return cnt


@bp.route('/uas', methods=['POST'])
@admin_required
def create_ua():
    ok, data, msg, code = load_ua(request.get_json(silent=True) or {})
    if not ok:
        return error(message=msg, code=code, status=400)
    ua = PoolUa(user_id=request.current_user.id, is_system=True, **data)
    db.session.add(ua)
    db.session.commit()
    return success(ua.to_dict(), message='添加成功', status=201)


@bp.route('/uas/<int:ua_id>', methods=['PUT'])
@admin_required
def update_ua(ua_id):
    ua = db.session.get(PoolUa, ua_id)
    if not ua:
        return error(message='UA 模板不存在', code=4040, status=404)
    payload = request.get_json(silent=True) or {}
    if str(payload.get('content') or '').strip():
        # 全量路径：content 在场时走统一校验，content/remark 一并收编
        ok, data, msg, code = load_ua(payload)
        if not ok:
            return error(message=msg, code=code, status=400)
        for k, v in data.items():
            setattr(ua, k, v)
    elif 'remark' in payload:
        # 局部更新（如仅改备注）：content 未提供则保留原值，避免必填校验误伤
        ua.remark = str(payload.get('remark') or '').strip()[:255]
    db.session.commit()
    return success(ua.to_dict(), message='保存成功')


@bp.route('/uas/<int:ua_id>', methods=['DELETE'])
@admin_required
def delete_ua(ua_id):
    ua = db.session.get(PoolUa, ua_id)
    if not ua:
        return error(message='UA 模板不存在', code=4040, status=404)
    refs = _ua_ref_count(ua.id)
    if refs:
        return error(message=f'该 UA 模板被 {refs} 个配置套引用，无法删除',
                     code=4311, data={'refs': refs}, status=409)
    db.session.delete(ua)
    db.session.commit()
    return success(message='删除成功')


@bp.route('/uas/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_uas():
    ids = (request.get_json(silent=True) or {}).get('ids') or []
    rows = PoolUa.query.filter(PoolUa.id.in_(ids)).all() if ids else []
    for ua in rows:
        refs = _ua_ref_count(ua.id)
        if refs:
            return error(message=f'「{ua.remark or ua.id}」被 {refs} 个配置套引用，整批未删除',
                         code=4311, data={'refs': refs}, status=409)
    for ua in rows:
        db.session.delete(ua)
    db.session.commit()
    return success(message=f'已删除 {len(rows)} 条')


# ---------------- 推送凭证池（Fernet 加密落库 / 脱敏回显 / 占位更新） ----------------

def _cred_ref_count(cred_id):
    """扫描配置体 push.credIds 引用计数"""
    cnt = 0
    for cs in ConfigSet.query.all():
        ids = ((cs.config or {}).get('push') or {}).get('credIds') or {}
        if cred_id in ids.values():
            cnt += 1
    return cnt


@bp.route('/credentials', methods=['POST'])
@token_required
def create_credential():
    payload = request.get_json(silent=True) or {}
    ok, data, msg, code = load_credential(payload)
    if not ok:
        return error(message=msg, code=code, status=400)
    c = PoolCredential(user_id=request.current_user.id, channel=data['channel'],
                       name=data['name'],
                       secret_enc=encrypt(json.dumps(data['fields'], ensure_ascii=False)))
    db.session.add(c)
    db.session.commit()
    return success({'id': c.id, 'channel': c.channel, 'name': c.name,
                    'fields': mask_fields(data['fields']), 'enabled': True},
                   message='添加成功', status=201)


@bp.route('/credentials/<int:cred_id>', methods=['PUT'])
@token_required
def update_credential(cred_id):
    c = PoolCredential.query.filter_by(id=cred_id, user_id=request.current_user.id).first()
    if not c:
        return error(message='凭证不存在', code=4040, status=404)
    ok, data, msg, code = load_credential_update(request.get_json(silent=True) or {})
    if not ok:
        return error(message=msg, code=code, status=400)

    try:
        old_fields = json.loads(decrypt(c.secret_enc))
    except Exception:
        old_fields = {}
    channel_changed = data.get('channel', c.channel) != c.channel
    merged = {} if channel_changed else dict(old_fields)
    merged.update(data.get('fields') or {})
    missing = required_missing(data.get('channel', c.channel), merged)
    if missing:
        return error(message=f'缺少必填项：{" / ".join(missing)}（密文占位不覆盖旧值，请填写新值）',
                     code=4321, status=400)
    if 'channel' in data:
        c.channel = data['channel']
    if 'name' in data:
        c.name = data['name']
    c.secret_enc = encrypt(json.dumps(merged, ensure_ascii=False))
    db.session.commit()
    return success({'id': c.id, 'channel': c.channel, 'name': c.name,
                    'fields': mask_fields(merged), 'enabled': bool(c.enabled)},
                   message='保存成功')


@bp.route('/credentials/<int:cred_id>', methods=['DELETE'])
@token_required
def delete_credential(cred_id):
    c = PoolCredential.query.filter_by(id=cred_id, user_id=request.current_user.id).first()
    if not c:
        return error(message='凭证不存在', code=4040, status=404)
    refs = _cred_ref_count(c.id)
    if refs:
        return error(message=f'该凭证被 {refs} 个配置套引用，无法删除',
                     code=4323, data={'refs': refs}, status=409)
    db.session.delete(c)
    db.session.commit()
    return success(message='删除成功')
