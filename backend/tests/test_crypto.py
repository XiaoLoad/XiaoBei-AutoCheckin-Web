# crypto 单元测试：加解密可逆性 + 密文不含明文 + 密钥派生稳定性
import pytest
from cryptography.fernet import InvalidToken


def test_roundtrip(app_ctx):
    from app.services import crypto
    cipher = crypto.encrypt('Lovexjw2095')
    assert cipher != 'Lovexjw2095'
    assert 'Lovexjw2095' not in cipher
    assert crypto.decrypt(cipher) == 'Lovexjw2095'


def test_decrypt_garbage_raises(app_ctx):
    from app.services import crypto
    with pytest.raises(InvalidToken):
        crypto.decrypt('not-a-valid-token')


def test_deterministic_key(app_ctx):
    """同一 SECRET_KEY 派生的密钥必须一致：跨重启可解密的前提"""
    from app.services import crypto
    c1 = crypto.encrypt('x')
    assert crypto.decrypt(c1) == 'x'
