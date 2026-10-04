# 凭据加密工具：B 平台密码 / 推送凭证的静态加密（Fernet 对称加密）
# 密钥不从明文存储，而是由 SECRET_KEY 经 HKDF-SHA256 派生——泄露数据库不解出凭据，
# 泄露 SECRET_KEY 才可能；密钥派生含版本盐，未来轮换口径时递增版本即可。
import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from flask import current_app

_HKDF_SALT = b'xiaobei-bp-cred-v1'
_HKDF_INFO = b'b-platform-credentials'


def _fernet():
    secret = current_app.config['SECRET_KEY'].encode('utf-8')
    derived = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=_HKDF_SALT, info=_HKDF_INFO
    ).derive(secret)
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt(plain: str) -> str:
    """明文 → ASCII 密文（urlsafe base64 token）"""
    return _fernet().encrypt(plain.encode('utf-8')).decode('ascii')


def decrypt(cipher: str) -> str:
    """ASCII 密文 → 明文；密钥不符或数据损坏抛 InvalidToken"""
    return _fernet().decrypt(cipher.encode('ascii')).decode('utf-8')
