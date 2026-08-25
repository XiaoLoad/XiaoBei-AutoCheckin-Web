# B 平台适配器工厂：默认真实实现；配置 USE_STUB_BPLATFORM=true 时切离线桩（联调降级用）
from app.services.b_platform.base import BPlatformError, VerifyResult, CheckinResult  # noqa: F401


def get_adapter():
    import os
    if (os.getenv('USE_STUB_BPLATFORM') or '').lower() in ('1', 'true'):
        from app.services.b_platform.stub import StubAdapter
        return StubAdapter()
    from app.services.b_platform.real import RealAdapter
    return RealAdapter()
