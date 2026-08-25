# Stub 适配器：完全离线的假实现（联调后端不可达时的降级开关）
from app.services.b_platform.base import CheckinResult, VerifyResult


class StubAdapter:
    name = 'stub'

    def verify_and_fetch(self, username, password, ua=None):
        return VerifyResult(
            ok=True, token='stub-token', bp_uid=1,
            profile={
                'name': '桩用户', 'college': '信息科学与工程学院', 'major': '软件工程',
                'className': '软工2301', 'studentNo': '2023010100',
                'school': '', 'phone': '', 'sex': None, 'enrollDate': '',
            },
        )

    def checkin(self, session, task):
        return CheckinResult(ok=True, status='success', detail={'stub': True})

    def fetch_records(self, session, account):
        return []
