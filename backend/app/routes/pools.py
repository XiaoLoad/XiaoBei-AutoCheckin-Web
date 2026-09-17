# 平台资源池蓝图：四池聚合读取 + 位置池 CRUD。
# 可见性口径：is_system=1 全员可读、仅 admin 可写；私有行严格 user_id 隔离。
import json
from types import SimpleNamespace

from flask import Blueprint, request

from app.extensions import db
from app.models import (BAccount, ConfigSet, ImageGroup, PoolCredential, PoolImage,
                        PoolLocation, PoolUa)
from app.models.b_account import binding_cred_id
from app.schemas.pools_schema import (load_credential, load_credential_update,
                                      load_location, load_ua,
                                      mask_fields, required_missing)
from app.services.crypto import decrypt, encrypt
from app.services.push_render import build_ctx, send_channel
from app.utils.auth import admin_required, token_required
from app.utils.response import error, success

bp = Blueprint('pools', __name__, url_prefix='/api/pools')


def _cred_dict(c):
    try:
        fields = json.loads(decrypt(c.secret_enc))
    except Exception:
        fields = {}
    return {'id': c.id, 'channel': c.channel, 'name': c.name,
            'fields': mask_fields(fields), 'enabled': bool(c.enabled)}


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

    return success({
        'locations': [l.to_dict() for l in locs],
        'images': [{'id': i.id, 'name': i.orig_name,
                    'sizeKb': round((i.size or 0) / 1024), 'mime': i.mime,
                    'groupId': i.group_id,
                    'inTrash': i.status == 'trash',
                    'used': i.status == 'used'} for i in imgs],
        'imageGroups': [{'id': g.id, 'name': g.name} for g in groups],
        'credentials': [_cred_dict(c) for c in creds],
        'uas': [u.to_dict() for u in uas],
    })


@bp.route('/credentials', methods=['GET'])
@token_required
def list_credentials():
    """凭证单拉：账号推送绑定等只需要凭证列表的场景使用，避免连带拉取图库等全量资源池"""
    user = request.current_user
    creds = (PoolCredential.query.filter_by(user_id=user.id)
             .order_by(PoolCredential.id.asc()).all())
    return success({'items': [_cred_dict(c) for c in creds]})


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

def _ref_index():
    """一次性加载全部配置套（数量有界），供引用计数复用，避免重复全表扫描"""
    return ConfigSet.query.all()


def _ua_ref_count(config_sets, ua_id):
    """扫描配置体 advanced.uaTemplateId 引用计数（配置套已一次性载入，复用即可）"""
    return sum(1 for cs in config_sets
               if ((cs.config or {}).get('advanced') or {}).get('uaTemplateId') == ua_id)


def _cred_ref_count(config_sets, cred_id):
    """扫描配置体 push.credIds 引用计数（配置套已一次性载入，复用即可）"""
    return sum(1 for cs in config_sets
               if cred_id in (((cs.config or {}).get('push') or {}).get('credIds') or {}).values())


def _acc_cred_ref_count(accounts, cred_id):
    """扫描账号级推送绑定引用计数（b_accounts.push_cred_json）。
    账号自带凭证是配置套之外的第二种引用来源，漏统计会让删除后留下悬空绑定。"""
    return sum(1 for a in accounts
               if cred_id in {binding_cred_id(v) for v in (a.push_creds or {}).values()})


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
    config_sets = _ref_index()
    refs = _ua_ref_count(config_sets, ua.id)
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
    config_sets = _ref_index()
    for ua in rows:
        refs = _ua_ref_count(config_sets, ua.id)
        if refs:
            return error(message=f'「{ua.remark or ua.id}」被 {refs} 个配置套引用，整批未删除',
                         code=4311, data={'refs': refs}, status=409)
    for ua in rows:
        db.session.delete(ua)
    db.session.commit()
    return success(message=f'已删除 {len(rows)} 条')


# ---------------- 推送凭证池（Fernet 加密落库 / 脱敏回显 / 占位更新） ----------------

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
    refs = _cred_ref_count(_ref_index(), c.id)
    acc_refs = _acc_cred_ref_count(BAccount.query.all(), c.id)
    used = []
    if refs:
        used.append(f'{refs} 个配置套')
    if acc_refs:
        used.append(f'{acc_refs} 个账号')
    if used:
        return error(message=f'该凭证被{"、".join(used)}引用，无法删除',
                     code=4323, data={'refs': refs, 'accountRefs': acc_refs}, status=409)
    db.session.delete(c)
    db.session.commit()
    return success(message='删除成功')


def _cred_key_of(channel, fields):
    """从解密后的字段取出单通道密钥（serverchan/pushplus 用字符串；email 用字段字典）。"""
    if channel == 'serverchan':
        return fields.get('serverchanKey') or None
    if channel == 'pushplus':
        return fields.get('pushplusToken') or None
    if channel == 'pushplus-open':
        return fields.get('token') or None
    if channel == 'email':
        if fields.get('emailSmtp') and fields.get('emailFrom') and fields.get('emailTo'):
            return {k: fields.get(k) for k in ('emailSmtp', 'emailFrom', 'emailPass', 'emailTo')}
    return None


@bp.route('/credentials/<int:cred_id>/test-push', methods=['POST'])
@token_required
def test_push_credential(cred_id):
    """用该凭证真实发送一条测试推送，验证通道可用性。仅发送凭证自身通道。"""
    c = PoolCredential.query.filter_by(id=cred_id, user_id=request.current_user.id).first()
    if not c:
        return error(message='凭证不存在', code=4040, status=404)
    try:
        fields = json.loads(decrypt(c.secret_enc))
    except Exception:
        return error(message='凭证密钥解析失败', code=4322, status=400)

    payload = request.get_json(silent=True) or {}
    template = payload.get('template') or 'html'
    if c.channel == 'pushplus-open':
        # 开放接口走 qq 通道：token 必填，qqCode 省略则发给机器人绑定的本人（自测可用性）。
        # QQ 仅支持 markdown/txt，强制 markdown，避免 html 在 QQ 里显示成源码。
        key = {'token': fields.get('token'), 'qqCode': payload.get('qqCode')}
        send_channel_name = 'qq'
        template = 'markdown'
    else:
        key = _cred_key_of(c.channel, fields)
        if key is None:
            return error(message=f'凭证缺少 {c.channel} 必要字段', code=4321, status=400)
        send_channel_name = c.channel

    # 样例上下文：用本人首个账号信息贴近真实效果；无账号则用占位，避免测试受限于是否有账号
    acc = BAccount.query.filter_by(user_id=request.current_user.id).order_by(BAccount.id.asc()).first()
    if acc is None:
        acc = SimpleNamespace(profile={}, account='测试账号')
    schedule = SimpleNamespace(task_type='dorm')
    resolved = {'time': {'startHour': 8, 'endHour': 22},
                'locationId': None,
                'remarks': ['这是一条测试推送，用于验证通道可用性']}
    ctx = build_ctx(acc, schedule, resolved, 'success', image_url='')
    ok, err = send_channel(send_channel_name, key, ctx, template)
    if ok:
        return success(message='测试推送已发送，请查收')
    return error(message=f'测试推送失败：{err}', code=4324, status=400)
