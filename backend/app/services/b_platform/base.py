# B 平台适配器公共载体：错误分类与结果结构
from dataclasses import dataclass, field


class BPlatformError(Exception):
    """B 平台交互异常。kind 用于上层分类处理：
    network=网络不可达 / credential=凭证或验证码错误 / captcha=验证码环节失败 / unknown=其它"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message

    def __str__(self):
        return self.message


@dataclass
class VerifyResult:
    ok: bool
    token: str = ''
    bp_uid: int = None
    profile: dict = field(default_factory=dict)


@dataclass
class CheckinResult:
    ok: bool
    status: str = 'success'      # success | fail | skip
    fail_reason: str = ''
    detail: dict = field(default_factory=dict)
