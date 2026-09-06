# 教务系统适配器工厂（风格同 b_platform）：默认真实实现；USE_STUB_JWXT=true 切离线桩。
from app.services.jwxt.base import JwxtError, TimetableEntry  # noqa: F401


def get_client():
    import os
    if (os.getenv('USE_STUB_JWXT') or '').lower() in ('1', 'true'):
        from app.services.jwxt.stub import StubJwxtClient
        return StubJwxtClient()
    from app.services.jwxt.real import RealJwxtClient
    return RealJwxtClient()
