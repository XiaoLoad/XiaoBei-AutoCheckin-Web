# 强智教务页面解析器单测：fixtures 为 2026-09-06 实抓的真实页面
# （学期理论课表全学期合并视图 + 教学周历），断言口径与人工核对结果一致。
import os
from datetime import date

import pytest

from app.services.jwxt.parser import (parse_current_semester, parse_timetable,
                                      parse_week_calendar)

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def _load(name):
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as f:
        return f.read()


@pytest.fixture(scope='module')
def entries():
    return parse_timetable(_load('jwxt_xskb_2026-2027-1.html'))


def _find(entries, **kw):
    return [e for e in entries
            if all(getattr(e, k) == v for k, v in kw.items())]


def test_parse_current_semester_defaults_to_selected_option():
    assert parse_current_semester(_load('jwxt_xskb_2026-2027-1.html')) == '2026-2027-1'


def test_parse_week_calendar_week1_monday_and_total():
    monday, total = parse_week_calendar(_load('jwxt_jxzl_2026-2027-1.html'), '2026-2027-1')
    assert monday == date(2026, 9, 7)
    assert total == 25


def test_timetable_dedupes_to_nine_logical_courses(entries):
    # 原始网格 24 条（跨大节重复渲染），去重后 9 条逻辑课程
    assert len(entries) == 9


def test_monday_web_course_full_span(entries):
    hit = _find(entries, weekday=1, course='Web开发技术课程设计')
    assert len(hit) == 1
    e = hit[0]
    assert e.weeks == [1, 2]
    assert e.sections == [1, 2, 3, 4, 5, 6, 7, 8]
    assert e.teacher == '李路加'
    assert e.room == '厚德楼306'


def test_tuesday_cell_three_entries_across_weeks(entries):
    # 周二同一大节格三条课（跨周共用格子）：移动(第3周) / Web(第1-2周) / 移动(第4周)
    tue = [e for e in entries if e.weekday == 2]
    assert len(tue) == 3
    mobile = _find(tue, course='移动应用开发技术课程设计')
    assert sorted(w for e in mobile for w in e.weeks) == [3, 4]
    assert all(e.sections == [1, 2, 3, 4, 5, 6, 7, 8] for e in tue)
    assert {e.room for e in tue} == {'厚德楼401', '厚德楼407'}


def test_wednesday_thursday_mobile_blocks(entries):
    wed = _find(entries, weekday=3)
    assert {tuple(e.weeks) for e in wed} == {(3,), (4,)}
    assert all(e.sections == [1, 2, 3, 4] and e.room == '厚德楼403' for e in wed)
    thu = _find(entries, weekday=4, course='移动应用开发技术课程设计')
    assert len(thu) == 1
    assert thu[0].weeks == [3, 5]
    assert thu[0].sections == [5, 6, 7, 8]
    assert thu[0].room == '厚德楼304'


def test_sunday_courses_without_room(entries):
    grad = _find(entries, weekday=7, course='毕业实习')
    assert len(grad) == 1
    assert grad[0].weeks == [13, 14, 15, 16, 17, 18]
    assert grad[0].sections == [1, 2]
    assert grad[0].teacher == '罗雯月'
    assert grad[0].room == ''
    situation = _find(entries, weekday=7, course='形势与政策4')
    assert len(situation) == 1
    assert situation[0].weeks == [5, 6]
    assert situation[0].sections == [3, 4]
    assert situation[0].teacher == '肖和平'


def test_expand_weeks_expressions():
    from app.services.jwxt.parser import _expand_weeks
    assert _expand_weeks('1-2') == [1, 2]
    assert _expand_weeks('3,5') == [3, 5]
    assert _expand_weeks('3,5-7') == [3, 5, 6, 7]
    assert _expand_weeks('13-18') == list(range(13, 19))


def test_parse_sections_enumeration_and_range():
    from app.services.jwxt.parser import _parse_sections
    assert _parse_sections('01-02-03-04-05-06-07-08') == [1, 2, 3, 4, 5, 6, 7, 8]
    assert _parse_sections('01-02') == [1, 2]
    assert _parse_sections('1-8') == [1, 2, 3, 4, 5, 6, 7, 8]   # 非零填充两段按区间


def test_week_type_normalization_and_odd_even_filter():
    from app.services.jwxt.parser import _parse_entry
    # 周类型 "周"/"每周" 等价全部；"单"/"双" 过滤奇偶（设计文档 §2.7③）
    e1 = _parse_entry(['高等数学[64][必修]', '张三', '计科1班(30)', '1-16(周)[01-02节]', '一教101'])
    assert e1.weeks == list(range(1, 17))
    e2 = _parse_entry(['大学英语[32][必修]', '李四', '计科1班(30)', '1-16(单)[03-04节]'])
    assert e2.weeks == [1, 3, 5, 7, 9, 11, 13, 15]
    e3 = _parse_entry(['体育[32][必修]', '王五', '计科1班(30)', '1-16(双)[05-06节]', '操场'])
    assert e3.weeks == [2, 4, 6, 8, 10, 12, 14, 16]
    assert e3.room == '操场'
