# 群推送分组模型：班级/寝室两类分组 + 合并推送审计 + 待触发护栏
# 两类分组共用同一套聚合与发送逻辑，差异只在成员来源：
#   class：成员派生自 account.profile.className == group.name（不存成员，始终同步）
#   dorm ：成员存于 push_group_members（手动维护）
# 触发策略见 docs/dorm-group-digest-design.md v3：基于任务时间窗，最晚任务窗结束 + 缓冲即收齐，无需 EOD 兜底
from app.extensions import db
from app.models.user import now_cst


class PushGroup(db.Model):
    __tablename__ = 'push_groups'

    TYPE_CLASS = 'class'
    TYPE_DORM = 'dorm'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    type = db.Column(db.String(16), nullable=False)                    # class | dorm
    name = db.Column(db.String(64), nullable=False)
    # pushplus qqBot 配置编码（option 路由键）；空=未绑定不推送
    qq_code = db.Column(db.String(32))
    # 图库归属：本分组绑定的图库分组（image_groups.id）。配置套图片策略选「按分组取图」时，
    # 组内账号按此取图；NULL=未绑定，运行时回退配置套默认图库（再回退全部图库）。
    # ondelete=SET NULL：图库分组被删时自动解绑，不阻塞删除
    image_group_id = db.Column(db.Integer,
                               db.ForeignKey('image_groups.id', ondelete='SET NULL'),
                               index=True)
    created_at = db.Column(db.DateTime, default=now_cst)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'type', 'name', name='uq_push_groups_user_type_name'),
    )

    # dorm 组手动维护成员；class 组不需要成员表
    members = db.relationship('PushGroupMember', back_populates='group', lazy='select',
                              cascade='all, delete-orphan')

    @property
    def bound(self) -> bool:
        """是否已绑定 QQ 群（绑定后才参与合并推送）。"""
        return bool(self.qq_code)

    def to_dict(self, member_count=None):
        return {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'qqCode': self.qq_code or '',
            'bound': self.bound,
            'imageGroupId': self.image_group_id,
            'memberCount': member_count if member_count is not None else len(self.members or []),
            'createdAt': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }


class PushGroupMember(db.Model):
    __tablename__ = 'push_group_members'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    group_id = db.Column(db.Integer,
                         db.ForeignKey('push_groups.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('b_accounts.id'), nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('group_id', 'account_id', name='uq_push_group_members_group_account'),
    )

    group = db.relationship('PushGroup', back_populates='members', lazy='select')
    account = db.relationship('BAccount', lazy='select')


class PushGroupDigestLog(db.Model):
    """合并推送审计：同组同天唯一约束作幂等护栏，保证只发一次。"""
    __tablename__ = 'push_group_digest_log'

    STATUS_SUCCESS = 'success'
    STATUS_FAIL = 'fail'
    STATUS_PARTIAL = 'partial'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    group_id = db.Column(db.Integer,
                         db.ForeignKey('push_groups.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    sent_at = db.Column(db.DateTime, default=now_cst)
    status = db.Column(db.String(16), nullable=False, default=STATUS_SUCCESS)  # success | fail | partial
    member_total = db.Column(db.Integer, nullable=False, default=0)            # 应签人数
    member_done = db.Column(db.Integer, nullable=False, default=0)             # 已签人数
    message = db.Column(db.String(255))                                       # fail 时填异常信息

    __table_args__ = (
        db.UniqueConstraint('group_id', 'date', name='uq_push_group_digest_log_group_date'),
    )


class PushGroupDigestPending(db.Model):
    """待触发护栏：记录每组当天应在 flush_at 触发合并推送；reconcile 兜底（防延迟 job 丢失，非 EOD 补发）。"""
    __tablename__ = 'push_group_digest_pending'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    group_id = db.Column(db.Integer,
                         db.ForeignKey('push_groups.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    flush_at = db.Column(db.DateTime, nullable=False)   # 计划触发时刻（最晚任务窗结束 + 缓冲）

    __table_args__ = (
        db.UniqueConstraint('group_id', 'date', name='uq_push_group_digest_pending_group_date'),
    )
