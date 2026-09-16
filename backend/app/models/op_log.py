# 操作日志：平台用户的关键操作流水（登录/登出/用户与权限变更），供管理员审计。
# 与 SignRecord 分工不同：SignRecord 记「机器替用户做了什么」（签到执行结果），
# 本表记「人做了什么」（谁在什么时候改了谁），两者共同构成完整的可追溯链。
# 写入走事件总线订阅者（app/services/op_log.py），发布点无需感知本表；
# 漏订阅只会表现为某类操作无日志，不影响主流程。
# username/role 存事件发生时的快照：用户被改名或改角色后，历史日志仍应显示当时的身份
# （否则「张三把李四禁用了」会随李四改名而变成另一个人做的）。
# user_id 可空：登录失败（账号不存在/密码错误/账号禁用）时无归属用户，但同样要留痕。
import json

from app.extensions import db
from app.models.user import now_cst


class OpLog(db.Model):
    __tablename__ = 'op_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    username = db.Column(db.String(64), nullable=False, default='')        # 操作者用户名快照
    role = db.Column(db.String(16), nullable=False, default='')            # 操作者角色快照
    action = db.Column(db.String(48), nullable=False)                      # login / user.disable ...
    category = db.Column(db.String(24), nullable=False)                    # auth | user
    result = db.Column(db.String(16), nullable=False, default='success')   # success | fail
    summary = db.Column(db.String(255), nullable=False, default='')        # 一句话描述（列表主文案）
    # 变更明细（JSON 字符串）：如改角色时记录 from/to。用 Text 而非 db.JSON，
    # 与 SignRecord.config_snapshot 一致，避免 MySQL/其他方言的 JSON 类型差异
    detail = db.Column(db.Text)
    ip = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    # 索引：清理 job 按 created_at 范围 DELETE，列表按 created_at 倒序分页
    created_at = db.Column(db.DateTime, default=now_cst, index=True)

    __table_args__ = (
        db.Index('ix_op_logs_category_time', 'category', 'created_at'),
        db.Index('ix_op_logs_user_time', 'user_id', 'created_at'),
    )

    def set_detail(self, data):
        """写入变更明细（dict→JSON）；None/空表示无明细。"""
        self.detail = json.dumps(data, ensure_ascii=False) if data else None

    def get_detail(self):
        """读出变更明细；非法或为空返回 None。"""
        if not self.detail:
            return None
        try:
            return json.loads(self.detail)
        except (ValueError, TypeError):
            return None

    def to_dict(self):
        return {
            'id': self.id,
            'userId': self.user_id,
            'username': self.username or '',
            'role': self.role or '',
            'action': self.action or '',
            'category': self.category or '',
            'result': self.result or 'success',
            'summary': self.summary or '',
            'detail': self.get_detail(),
            'ip': self.ip or '',
            'userAgent': self.user_agent or '',
            'createdAt': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else '',
        }
