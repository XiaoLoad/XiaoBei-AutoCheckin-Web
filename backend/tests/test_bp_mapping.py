# 学生信息字段映射：fixture 即用户提供的真实响应体片段（截取自抓包）
from app.services.b_platform.real import map_student_info

SAMPLE_DATA = {
    "id": 977052,
    "studentNumber": "2025304262",
    "deptName": "25计算机（专升本）14班",
    "studentName": "肖街伟",
    "studentIpone": "18290449672",
    "studentState": 0,
    "studentIdCard": "500233200308198854",
    "studentSex": 0,
    "studentSchoolTime": "2025-09-01",
    "paasword": "1",
    "schoolId": 9269,
    "schoolName": "重庆城市科技学院",
    "collegeName": "人工智能与大数据学院",
    "professionalName": "计算机科学与技术（专升本）",
}


def test_standard_keys_mapped():
    profile, bp_uid = map_student_info(SAMPLE_DATA)
    assert bp_uid == 977052
    assert profile['name'] == '肖街伟'
    assert profile['college'] == '人工智能与大数据学院'
    assert profile['major'] == '计算机科学与技术（专升本）'
    assert profile['className'] == '25计算机（专升本）14班'
    assert profile['studentNo'] == '2025304262'
    assert profile['school'] == '重庆城市科技学院'
    assert profile['phone'] == '18290449672'
    assert profile['enrollDate'] == '2025-09-01'


def test_sensitive_fields_dropped():
    """身份证号与回显密码绝不进入 profile"""
    profile, _ = map_student_info(SAMPLE_DATA)
    dumped = str(profile)
    assert '500233200308198854' not in dumped
    assert 'paasword' not in dumped
