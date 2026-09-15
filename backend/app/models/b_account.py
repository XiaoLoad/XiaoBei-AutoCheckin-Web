# B 平台账号模型：登录凭据（加密存储）+ 平台回填档案 + 会话票据 + 最近签到聚合
import json

from app.extensions import db
from app.models.user import now_cst
from app.services import crypto

# 账号可绑定的推送通道（与配置套 push.channels 取值一致）
PUSH_CHANNELS = ('serverchan', 'pushplus', 'email')


def binding_cred_id(raw):
    """绑定项取凭证 id：兼容纯 id 与 email 的 {credId?, to} 两种形态。
    取不到或非法一律 None（调度解析与凭证引用计数共用，避免两处各判一次）。"""
    if isinstance(raw, dict):
        raw = raw.get('credId')
    if isinstance(raw, bool):
        return None
    try:
        cid = int(raw)
    except (TypeError, ValueError):
        return None
    return cid if cid > 0 else None


class BAccount(db.Model):
    __tablename__ = 'b_accounts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    # 登录标识：手机号或身份证号（B 平台服务端识别），本系统不做格式强校验
    account = db.Column(db.String(64), nullable=False)
    password_enc = db.Column(db.Text, nullable=False)       # Fernet 密文
    platform = db.Column(db.String(32), nullable=False, default='B 打卡平台')
    # 已废弃：界面建的账号一律落到缺省 'general'（新增/编辑弹窗无此字段，前端从不提交），
    # 读它作展示会让所有账号长同一个标签。类型请由 sign_tasks() 派生（前端 utils/accountType.js）。
    # 保留该列是因为同项目 App 端可能仍在消费，删列属契约破坏。
    type = db.Column(db.String(16), nullable=False, default='general')
    enabled = db.Column(db.Boolean, nullable=False, default=True)

    # 平台回填档案（JSON 字典，键见 b_platform.real.map_student_info）
    profile_json = db.Column(db.Text)
    bp_uid = db.Column(db.BigInteger)                        # B 平台用户 ID
    token_enc = db.Column(db.Text)                           # B 平台会话 token（Fernet 密文）
    token_updated_at = db.Column(db.DateTime)

    verify_status = db.Column(db.String(16), nullable=False, default='unverified')  # unverified|ok|fail
    verified_at = db.Column(db.DateTime)

    last_sign_at = db.Column(db.DateTime)
    last_sign_status = db.Column(db.String(16))              # success|fail|skip

    # 账号级推送凭证绑定：JSON {channel: 绑定项}，channel ∈ PUSH_CHANNELS。
    # 绑定项为凭证 id，或 email 的 {credId?, to}（to=该账号的收件人，可多值逗号分隔）。
    # 配置套的凭证来源决定「用不用」，账号这里决定「用哪份凭证、邮件发给谁」。
    push_cred_json = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=now_cst)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'account', name='uq_baccounts_user_account'),
    )

    # 列表查询经 joinedload 预载，避免 to_dict/sign_tasks 内逐行查 schedules（N+1）
    schedules = db.relationship('Schedule', back_populates='account', lazy='select')

    EMPTY_PROFILE = {'name': '', 'college': '', 'major': '', 'className': '', 'studentNo': ''}

    # ---- 凭据加解密 ----
    def set_password(self, raw: str):
        self.password_enc = crypto.encrypt(raw)

    def get_password(self) -> str:
        return crypto.decrypt(self.password_enc)

    def set_token(self, token: str):
        self.token_enc = crypto.encrypt(token)
        self.token_updated_at = now_cst()

    def get_token(self):
        return crypto.decrypt(self.token_enc) if self.token_enc else None

    # ---- 档案读写 ----
    @property
    def profile(self) -> dict:
        if not self.profile_json:
            return dict(self.EMPTY_PROFILE)
        try:
            merged = dict(self.EMPTY_PROFILE)
            merged.update(json.loads(self.profile_json))
            return merged
        except (ValueError, TypeError):
            return dict(self.EMPTY_PROFILE)

    def set_profile(self, profile: dict):
        self.profile_json = json.dumps(profile, ensure_ascii=False)

    # ---- 推送凭证绑定（账号级）----
    @property
    def push_creds(self) -> dict:
        if not self.push_cred_json:
            return {}
        try:
            data = json.loads(self.push_cred_json)
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {}

    def set_push_creds(self, creds: dict):
        """只保留白名单通道且值非空的项（空对象与空值丢弃）；全空则置 NULL，不留空对象。"""
        cleaned = {k: v for k, v in (creds or {}).items() if k in PUSH_CHANNELS and v}
        self.push_cred_json = json.dumps(cleaned, ensure_ascii=False) if cleaned else None

    def sign_tasks(self):
        """该账号已添加至定时任务的签到类型及启用态（按 dorm/activity 固定顺序）。
        用于账号列表「类型」列与配置页账号树徽标动态派生，不依赖账号自身的 type 字段。
        schedules 由列表查询 joinedload 预载；单对象上下文按 FK 惰性加载一次，无 N+1。"""
        rows = self.schedules
        out = []
        for t in ('dorm', 'activity'):
            s = next((x for x in rows if x.task_type == t), None)
            out.append({
                'type': t,
                'enabled': bool(s.enabled) if s else False,
                'exists': s is not None,
                'configSetId': s.config_set_id if (s and s.config_set_id is not None) else None,
            })
        return out

    def to_dict(self):
        """输出前端 Account 契约形状（types.js），组件零改动对接"""
        return {
            'id': self.id,
            'account': self.account,
            'platform': self.platform,
            'type': self.type,          # 已废弃，勿用于展示；展示请读 signTasks
            'enabled': bool(self.enabled),
            'profile': self.profile,
            'pushCreds': self.push_creds,
            'signTasks': self.sign_tasks(),
            'lastSignIn': {
                'time': self.last_sign_at.strftime('%Y-%m-%d %H:%M') if self.last_sign_at else '',
                'status': self.last_sign_status or 'never',
            },
            'verifyStatus': self.verify_status,
            'createdAt': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }

    def __repr__(self):
        return f'<BAccount {self.account} user={self.user_id}>'
