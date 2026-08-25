# B 平台账号模型：登录凭据（加密存储）+ 平台回填档案 + 会话票据 + 最近签到聚合
import json

from app.extensions import db
from app.models.user import now_cst
from app.services import crypto


class BAccount(db.Model):
    __tablename__ = 'b_accounts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    # 登录标识：手机号或身份证号（B 平台服务端识别），本系统不做格式强校验
    account = db.Column(db.String(64), nullable=False)
    password_enc = db.Column(db.Text, nullable=False)       # Fernet 密文
    platform = db.Column(db.String(32), nullable=False, default='B 打卡平台')
    # 账号分类标签：dorm=寝室 activity=活动 general=通用（仅展示语义，任务类型见 schedules）
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

    created_at = db.Column(db.DateTime, default=now_cst)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'account', name='uq_baccounts_user_account'),
    )

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

    def to_dict(self):
        """输出前端 Account 契约形状（types.js），组件零改动对接"""
        return {
            'id': self.id,
            'account': self.account,
            'platform': self.platform,
            'type': self.type,
            'enabled': bool(self.enabled),
            'profile': self.profile,
            'lastSignIn': {
                'time': self.last_sign_at.strftime('%Y-%m-%d %H:%M') if self.last_sign_at else '',
                'status': self.last_sign_status or 'never',
            },
            'verifyStatus': self.verify_status,
            'createdAt': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }

    def __repr__(self):
        return f'<BAccount {self.account} user={self.user_id}>'
