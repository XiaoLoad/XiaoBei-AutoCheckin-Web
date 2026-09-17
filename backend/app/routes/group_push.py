# 群推送分组蓝图：班级（className 派生）/ 寝室（手动成员）两类分组的 CRUD、
# QQ 群绑定、成员管理与合并推送状态查询。触发与发送在 app/services/group_digest，本层只管配置与展示。
import json

from flask import Blueprint, request

from app.extensions import db
from app.models import (BAccount, PushGroup, PushGroupDigestLog, PushGroupMember)
from app.models.user import now_cst
from app.utils.response import error, success
from app.utils.auth import token_required
from app.services.crypto import decrypt, encrypt

bp = Blueprint('group_push', __name__, url_prefix='/api/group-push')


def _today_status(group_id):
    log = PushGroupDigestLog.query.filter_by(group_id=group_id, date=now_cst().date()).first()
    if not log:
        return None
    return {
        'status': log.status,
        'sentAt': log.sent_at.strftime('%Y-%m-%d %H:%M') if log.sent_at else '',
        'memberTotal': log.member_total,
        'memberDone': log.member_done,
        'message': log.message or '',
    }


def _member_count(g):
    if g.type == PushGroup.TYPE_CLASS:
        return BAccount.query.filter_by(user_id=g.user_id, enabled=True).filter(
            BAccount.profile_json.like(f'%"className": "{g.name}"%')).count()
    return PushGroupMember.query.filter_by(group_id=g.id).count()


def _dorm_to_dict(g):
    return {
        'id': g.id,
        'type': g.type,
        'name': g.name,
        'qqCode': g.qq_code or '',
        'bound': g.bound,
        'memberCount': _member_count(g),
        'today': _today_status(g.id),
        'createdAt': g.created_at.strftime('%Y-%m-%d %H:%M') if g.created_at else '',
    }


def _class_groups_derived(user_id):
    """班级分组实时派生：去重账号 className；已绑定的组回写 qq_code 与今日状态。"""
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
    # 默认 / dorm：显式建的行
    groups = (PushGroup.query.filter_by(user_id=uid, type=PushGroup.TYPE_DORM)
              .order_by(PushGroup.id.desc()).all())
    return success({'items': [_dorm_to_dict(g) for g in groups], 'type': PushGroup.TYPE_DORM})


@bp.route('/groups', methods=['POST'])
@token_required
def create_dorm_group():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get('name') or '').strip()
    if not name:
        return error(message='分组名称不能为空', code=4400, status=400)
    uid = request.current_user.id
    if PushGroup.query.filter_by(user_id=uid, type=PushGroup.TYPE_DORM, name=name).first():
        return error(message='该寝室分组已存在', code=4401, status=409)
    qq_code = str(payload.get('qqCode') or '').strip() or None
    g = PushGroup(user_id=uid, type=PushGroup.TYPE_DORM, name=name, qq_code=qq_code)
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
        new_name = str(payload['name']).strip()[:64]
        dup = PushGroup.query.filter_by(user_id=request.current_user.id,
                                        type=PushGroup.TYPE_DORM, name=new_name).first()
        if dup and dup.id != g.id:
            return error(message='该寝室分组名称已存在', code=4401, status=409)
        g.name = new_name
    if 'qqCode' in payload:
        g.qq_code = str(payload['qqCode'] or '').strip() or None
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
    g = PushGroup.query.filter_by(id=group_id, user_id=request.current_user.id,
                                  type=PushGroup.TYPE_DORM).first()
    if not g:
        return error(message='分组不存在', code=4040, status=404)
    payload = request.get_json(silent=True) or {}
    ids = payload.get('accountIds') or []
    if not isinstance(ids, list):
        return error(message='accountIds 须为数组', code=4402, status=400)
    added = 0
    for raw in ids:
        try:
            aid = int(raw)
        except (TypeError, ValueError):
            continue
        acc = BAccount.query.filter_by(id=aid, user_id=request.current_user.id).first()
        if not acc:
            continue
        if PushGroupMember.query.filter_by(group_id=group_id, account_id=aid).first():
            continue
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
    """班级分组绑定/解绑 QQ 群：按 (user_id, type=class, name) upsert；qq_code 为空则删除该行。"""
    payload = request.get_json(silent=True) or {}
    name = str(payload.get('name') or '').strip()
    if not name:
        return error(message='班级名称不能为空', code=4400, status=400)
    uid = request.current_user.id
    qq_code = str(payload.get('qqCode') or '').strip() or None
    g = PushGroup.query.filter_by(user_id=uid, type=PushGroup.TYPE_CLASS, name=name).first()
    if not qq_code:
        if g:
            db.session.delete(g)
            db.session.commit()
        return success({'name': name, 'qqCode': '', 'bound': False}, message='已解绑')
    if g is None:
        g = PushGroup(user_id=uid, type=PushGroup.TYPE_CLASS, name=name, qq_code=qq_code)
        db.session.add(g)
    else:
        g.qq_code = qq_code
    db.session.commit()
    return success({'id': g.id, 'name': name, 'qqCode': g.qq_code, 'bound': True},
                  message='已绑定')


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
        return error(message=f'发送失败：{e}', code=4405, status=500)
    return success({'today': _today_status(g.id)}, message='已触发发送')
