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

    def find_active_task(self, session, task_type):
        """联调桩：返回一个假的进行中任务，使调度链路测试可走通成功分支（无围栏、无需图）"""
        kind = 'know' if task_type == 'dorm' else 'sign'
        return {
            'task': {'id': 58088, 'kind': kind, 'type': task_type, 'taskName': '桩签到任务',
                     'startTime': '00:00:00', 'endTime': '23:59:59',
                     'needPhoto': False, 'finished': False},
            'fence': [],
        }

    def submit_checkin(self, session, task_type, platform_task_id, location, address, remark, image=None):
        return CheckinResult(ok=True, status='success', detail={'stub': True})

    def fetch_records(self, session, account):
        return []

    def fetch_history_tasks(self, token, kind, page_num=1, page_size=200):
        if kind == 'sign':
            return []
        return [{
            'id': 58088, 'kind': 'know', 'type': 'dorm',
            'taskName': '07.02查寝签到', 'startDate': '2026-06-07',
            'endDate': '2026-06-07', 'startTime': '00:00:00', 'endTime': '23:59:59',
            'initiator': '马一鸣 · 辅导员', 'needPhoto': True, 'finished': True,
        }]

    def fetch_active_tasks(self, token, task_type):
        """联调桩：寝/活各返回一条覆盖全天的进行中任务——寝室待签到、活动已签到，
        便于前端卡片在无网环境下同时看到两种状态与展开详情"""
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        kind = 'know' if task_type == 'dorm' else 'sign'
        signed = kind == 'sign'
        return [{
            'id': 58088 if kind == 'know' else 58089, 'kind': kind, 'type': task_type,
            'taskName': '桩已签到任务' if signed else '桩待签到任务',
            'startDate': today, 'endDate': today,
            'startTime': '00:00:00', 'endTime': '23:59:59',
            'initiator': '桩发起人 · 辅导员', 'needPhoto': kind == 'know', 'finished': signed,
        }]

    def fetch_task_detail(self, token, kind, task_id):
        return {
            'geoFence': [{
                'alias': '重庆城市科技学院巴南校区', 'latitude': '29.343984',
                'longitude': '106.534989', 'location': '龙洲湾街道…敬雅楼2栋', 'radius': '500',
            }],
            'task': {
                'id': task_id, 'kind': kind, 'type': 'dorm' if kind == 'know' else 'activity',
                'taskName': '07.02查寝签到', 'startDate': '2026-06-07', 'endDate': '2026-06-07',
                'startTime': '00:00:00', 'endTime': '23:59:59', 'initiator': '马一鸣 · 辅导员',
                'needPhoto': True, 'finished': True,
            },
        }

    def fetch_task_logs(self, token, kind, task_id):
        return [{
            'id': 19848643, 'studentNumber': '2025000000', 'studentName': '张三',
            'className': '', 'location': '106.5342415:29.3423784', 'remark': '打卡',
            'time': '2026-06-07 21:30:00', 'file': '', 'finished': True,
        }]
