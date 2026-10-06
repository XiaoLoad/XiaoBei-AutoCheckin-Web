# 分组蓝图：班级（className 派生）/ 寝室（手动成员）两类分组的 CRUD。
# 分组承载两项归属：QQ 群（合并推送用）与图库分组（配置套「按分组取图」用），
# 两者互相独立、各自可空。QQ 群绑定、成员管理与合并推送状态在此层；
# 触发与发送在 app/services/group_digest，图库归属的消费方在 scheduler。
import json

from flask import Blueprint, request
from sqlalchemy import func

from app.extensions import db
from app.models import (BAccount, ImageGroup, PushGroup, PushGroupDigestLog, PushGroupMember)
from app.models.user import now_cst
from app.utils.response import error, success
from app.utils.auth import token_required
from app.services.crypto import decrypt, encrypt

bp = Blueprint('group_push', __name__, url_prefix='/api/group-push')

# 与 push_groups 表列宽同源（name String(64)、qq_code String(32)）；
# create/class-bind 与 update 同口径截断，超长不再依赖 DB 层报 500
NAME_MAX = 64
QQ_CODE_MAX = 32


def _today_status(group_id):
    log = PushGroupDigestLog.query.filter_by(group_id=group_id, date=now_cst().date()).first()
    return _log_to_dict(log)


def _log_to_dict(log):
    if not log:
        return None
    return {
        'status': log.status,
        'sentAt': log.sent_at.strftime('%Y-%m-%d %H:%M') if log.sent_at else '',
        'memberTotal': log.member_total,
        'memberDone': log.member_done,
        'message': log.message or '',
    }


def _escape_like(s):
    return s.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def _member_count(g):
    if g.type == PushGroup.TYPE_CLASS:
        # profile_json 是 JSON 文本，班级名拼接进 LIKE 需转义通配符（分组名含 %/_ 时防误匹配）
        return BAccount.query.filter_by(user_id=g.user_id, enabled=True).filter(
            BAccount.profile_json.like(f'%"className": "{_escape_like(g.name)}"%',
                                       escape='\\')).count()
    return PushGroupMember.query.filter_by(group_id=g.id).count()


def _batch_member_counts(group_ids):
    """dorm 分组成员计数一次 GROUP BY 取回（列表页逐组 COUNT 的 2N+1 消除）。"""
    if not group_ids:
        return {}
    rows = (db.session.query(PushGroupMember.group_id,
                             func.count(PushGroupMember.id))
            .filter(PushGroupMember.group_id.in_(group_ids))
            .group_by(PushGroupMember.group_id).all())
    return dict(rows)


def _batch_today_status(group_ids):
    """今日推送状态一次 IN 取回（同上，消 2N+1）。"""
    if not group_ids:
        return {}
    logs = (PushGroupDigestLog.query.filter(PushGroupDigestLog.group_id.in_(group_ids),
                                            PushGroupDigestLog.date == now_cst().date())
            .all())
    return {l.group_id: _log_to_dict(l) for l in logs}


def _clean_image_group(uid, raw):
    """图库归属校验：空值（None/''/0）表示解绑；否则须是本人的图库分组。
    返回 (ok, image_group_id, message)。越权或不存在一律拒绝，避免脏数据进库。"""
    if raw in (None, '', 0, '0'):
        return True, None, ''
    try:
        gid = int(raw)
    except (TypeError, ValueError):
        return False, None, '图库分组 id 无效'
    if ImageGroup.query.filter_by(id=gid, user_id=uid).first() is None:
        return False, None, '图库分组不存在'
    return True, gid, ''


def _dorm_to_dict(g, member_count=None, today=None):
    return {
        'id': g.id,
        'type': g.type,
        'name': g.name,
        'qqCode': g.qq_code or '',
        'bound': g.bound,
        'imageGroupId': g.image_group_id,
        'memberCount': member_count if member_count is not None else _member_count(g),
        'today': today if today is not None else _today_status(g.id),
        'createdAt': g.created_at.strftime('%Y-%m-%d %H:%M') if g.created_at else '',
    }


def _class_groups_derived(user_id):
    """班级分组实时派生：去重账号 className；已建的行回写 qq_code、图库归属与今日状态。"""
    accs = BAccount.query.filter_by(user_id=user_id, enabled=True).all()
    names = []
    seen = set()
    for a in accs:
        cn = (a.profile or {}).get('className') or ''
        if cn and cn not in seen:
            seen.add(cn)
            names.append(cn)
    rows = (PushGroup.query.filter_by(user_id=user_id, type=PushGroup.TYPE_CLASS).all())
    by_name = {r.name: r for r in rows}
    out = []
    for name in names:
        g = by_name.get(name)
        out.append({
            'id': g.id if g else None,
            'type': PushGroup.TYPE_CLASS,
            'name': name,
            'qqCode': g.qq_code or '' if g else '',
            'bound': bool(g and g.bound),
            'imageGroupId': g.image_group_id if g else None,
            'memberCount': sum(1 for a in accs if (a.profile or {}).get('className') == name),
            'today': _today_status(g.id) if g else None,
            'createdAt': g.created_at.strftime('%Y-%m-%d %H:%M') if (g and g.created_at) else '',
        })
    return out


@bp.route('/groups', methods=['GET'])
@token_required
def list_groups():
    gtype = request.args.get('type')
    uid = request.current_user.id
    if gtype == PushGroup.TYPE_CLASS:
        return success({'items': _class_groups_derived(uid), 'type': PushGroup.TYPE_CLASS})
    # 默认 / dorm：显式建的行；成员数与今日状态各一次批量查询，避免逐组 2N+1
    groups = (PushGroup.query.filter_by(user_id=uid, type=PushGroup.TYPE_DORM)
              .order_by(PushGroup.id.desc()).all())
    gids = [g.id for g in groups]
    counts = _batch_member_counts(gids)
    todays = _batch_today_status(gids)
    items = [_dorm_to_dict(g, member_count=counts.get(g.id, 0), today=todays.get(g.id))
             for g in groups]
    return success({'items': items, 'type': PushGroup.TYPE_DORM})


@bp.route('/dorm-members', methods=['GET'])
@token_required
def dorm_members():
    """寝室分组成员地图：accountId → 所属分组，按分组 id 倒序（同分组页排列）。
    账号卡片要标注所属寝室分组，而账号列表接口不带这层归属；按分组逐个取成员会在
    账号页产生 N+1，故在此一次 join 返回。一个账号可能被加入多个分组，交由调用方取舍。"""
    uid = request.current_user.id
    rows = (db.session.query(PushGroupMember.account_id, PushGroup.id, PushGroup.name)
            .join(PushGroup, PushGroup.id == PushGroupMember.group_id)
            .filter(PushGroup.user_id == uid, PushGroup.type == PushGroup.TYPE_DORM)
            .order_by(PushGroup.id.desc()).all())
    items = [{'accountId': aid, 'groupId': gid, 'groupName': name} for aid, gid, name in rows]
    return success({'items': items})


@bp.route('/groups', methods=['POST'])
@token_required
def create_dorm_group():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get('name') or '').strip()[:NAME_MAX]
    if not name:
        return error(message='分组名称不能为空', code=4400, status=400)
    uid = request.current_user.id
    if PushGroup.query.filter_by(user_id=uid, type=PushGroup.TYPE_DORM, name=name).first():
        return error(message='该寝室分组已存在', code=4401, status=409)
    ok, image_gid, message = _clean_image_group(uid, payload.get('imageGroupId'))
    if not ok:
        return error(message=message, code=4402, status=400)
    qq_code = str(payload.get('qqCode') or '').strip()[:QQ_CODE_MAX] or None
    g = PushGroup(user_id=uid, type=PushGroup.TYPE_DORM, name=name, qq_code=qq_code,
                  image_group_id=image_gid)
    db.session.add(g)
    db.session.commit()
    return success(_dorm_to_dict(g), message='创建成功', status=201)


@bp.route('/groups/<int:group_id>', methods=['PUT'])
@token_required
def update_dorm_group(group_id):
    g = PushGroup.query.filter_by(id=group_id, user_id=request.current_user.id,
                                  type=PushGroup.TYPE_DORM).first()
    if not g:
        return error(message='分组不存在', code=4040, status=404)
    payload = request.get_json(silent=True) or {}
    if 'name' in payload and str(payload.get('name') or '').strip():
        new_name = str(payload['name']).strip()[:NAME_MAX]
        dup = PushGroup.query.filter_by(user_id=request.current_user.id,
                                        type=PushGroup.TYPE_DORM, name=new_name).first()
        if dup and dup.id != g.id:
            return error(message='该寝室分组名称已存在', code=4401, status=409)
        g.name = new_name
    if 'qqCode' in payload:
        g.qq_code = str(payload['qqCode'] or '').strip()[:QQ_CODE_MAX] or None
    if 'imageGroupId' in payload:
        ok, image_gid, message = _clean_image_group(request.current_user.id,
                                                    payload.get('imageGroupId'))
        if not ok:
            return error(message=message, code=4402, status=400)
        g.image_group_id = image_gid
    db.session.commit()
    return success(_dorm_to_dict(g), message='保存成功')


@bp.route('/groups/<int:group_id>', methods=['DELETE'])
@token_required
def delete_dorm_group(group_id):
    g = PushGroup.query.filter_by(id=group_id, user_id=request.current_user.id,
                                  type=PushGroup.TYPE_DORM).first()
    if not g:
        return error(message='分组不存在', code=4040, status=404)
    db.session.delete(g)
    db.session.commit()
    return success(message='已删除')


@bp.route('/groups/<int:group_id>/members', methods=['GET'])
@token_required
def list_members(group_id):
    g = PushGroup.query.filter_by(id=group_id, user_id=request.current_user.id,
                                  type=PushGroup.TYPE_DORM).first()
    if not g:
        return error(message='分组不存在', code=4040, status=404)
    rows = PushGroupMember.query.filter_by(group_id=group_id).all()
    acc_ids = [r.account_id for r in rows]
    accs = {a.id: a for a in BAccount.query.filter(BAccount.id.in_(acc_ids)).all()} if acc_ids else {}
    items = []
    for r in rows:
        a = accs.get(r.account_id)
        items.append({
            'accountId': r.account_id,
            'account': a.account if a else '(已删除)',
            'name': (a.profile if a else {}).get('name') or '',
            'className': (a.profile if a else {}).get('className') or '',
        })
    return success({'items': items})


@bp.route('/groups/<int:group_id>/members', methods=['POST'])
@token_required
def add_members(group_id):
    payload = request.get_json(silent=True) or {}
    ids = payload.get('accountIds') or []
    if not isinstance(ids, list):
        return error(message='accountIds 须为数组', code=4402, status=400)
    if len(ids) > 200:
        return error(message='单次添加不能超过 200 个成员', code=4402, status=400)
    g = PushGroup.query.filter_by(id=group_id, user_id=request.current_user.id,
                                  type=PushGroup.TYPE_DORM).first()
    if not g:
        return error(message='分组不存在', code=4040, status=404)

    # 批量解析：去重后 2 次查询取回有效账号与已有成员（原逐条 2N 次查询的长事务隐患）
    unique_ids = list(dict.fromkeys(
        aid for aid in (int(i) for i in ids if isinstance(i, int) or
                        (isinstance(i, str) and i.isdigit()))
    ))
    if not unique_ids:
        return success({'added': 0}, message='已添加 0 个成员')
    valid = {a.id for a in BAccount.query.filter(
        BAccount.id.in_(unique_ids), BAccount.user_id == request.current_user.id).all()}
    existing = {r.account_id for r in PushGroupMember.query.filter(
        PushGroupMember.group_id == group_id,
        PushGroupMember.account_id.in_(unique_ids)).all()}
    added = 0
    for aid in unique_ids:
        if aid in valid and aid not in existing:
            db.session.add(PushGroupMember(group_id=group_id, account_id=aid))
            added += 1
    db.session.commit()
    return success({'added': added}, message=f'已添加 {added} 个成员')


@bp.route('/groups/<int:group_id>/members/<int:account_id>', methods=['DELETE'])
@token_required
def remove_member(group_id, account_id):
    g = PushGroup.query.filter_by(id=group_id, user_id=request.current_user.id,
                                  type=PushGroup.TYPE_DORM).first()
    if not g:
        return error(message='分组不存在', code=4040, status=404)
    m = PushGroupMember.query.filter_by(group_id=group_id, account_id=account_id).first()
    if m:
        db.session.delete(m)
        db.session.commit()
    return success(message='已移除')


@bp.route('/class-bind', methods=['POST'])
@token_required
def bind_class_group():
    """班级分组保存：按 (user_id, type=class, name) upsert。
    qqCode 与 imageGroupId 各自独立、都可空，只传其一时另一个保持不变；
    两者皆空视为彻底解绑，删除该行（不留空壳，避免与派生的班级列表重名冲突）。"""
    payload = request.get_json(silent=True) or {}
    name = str(payload.get('name') or '').strip()[:NAME_MAX]
    if not name:
        return error(message='班级名称不能为空', code=4400, status=400)
    uid = request.current_user.id
    g = PushGroup.query.filter_by(user_id=uid, type=PushGroup.TYPE_CLASS, name=name).first()
    qq_code = g.qq_code if g else None
    image_gid = g.image_group_id if g else None
    if 'qqCode' in payload:
        qq_code = str(payload.get('qqCode') or '').strip()[:QQ_CODE_MAX] or None
    if 'imageGroupId' in payload:
        ok, image_gid, message = _clean_image_group(uid, payload.get('imageGroupId'))
        if not ok:
            return error(message=message, code=4402, status=400)
    if not qq_code and not image_gid:
        if g:
            db.session.delete(g)
            db.session.commit()
        return success({'name': name, 'qqCode': '', 'imageGroupId': None, 'bound': False},
                       message='已解绑')
    if g is None:
        g = PushGroup(user_id=uid, type=PushGroup.TYPE_CLASS, name=name)
        db.session.add(g)
    g.qq_code = qq_code
    g.image_group_id = image_gid
    db.session.commit()
    return success({'id': g.id, 'name': name, 'qqCode': g.qq_code or '',
                    'imageGroupId': g.image_group_id, 'bound': g.bound},
                   message='已保存')


@bp.route('/flush', methods=['POST'])
@token_required
def flush_now():
    """手动立即汇总发送（测试/补发）：按 type + id（dorm）/ name（class）解析分组后强刷。"""
    from app.services.group_digest import flush_digest
    payload = request.get_json(silent=True) or {}
    gtype = payload.get('type')
    uid = request.current_user.id
    g = None
    if gtype == PushGroup.TYPE_CLASS:
        name = str(payload.get('name') or '').strip()
        g = PushGroup.query.filter_by(user_id=uid, type=PushGroup.TYPE_CLASS, name=name).first()
    else:
        try:
            gid = int(payload.get('id'))
        except (TypeError, ValueError):
            return error(message='分组 id 无效', code=4403, status=400)
        g = PushGroup.query.filter_by(id=gid, user_id=uid, type=PushGroup.TYPE_DORM).first()
    if not g:
        return error(message='分组不存在', code=4040, status=404)
    if not g.bound:
        return error(message='该分组未绑定 QQ 群，无法发送', code=4404, status=400)
    try:
        flush_digest(g.id, now_cst().date(), force=True)
    except Exception as e:
        # 异常原文可能含内部路径/库信息，不透前端；完整堆栈进日志供排查
        import logging
        logging.getLogger('app').exception('群推送手动发送失败 group=%s', g.id)
        return error(message=f'发送失败：{type(e).__name__}', code=4405, status=500)
    return success({'today': _today_status(g.id)}, message='已触发发送')
