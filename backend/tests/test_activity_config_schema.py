# activity 专属配置块兜底清洗单测（config_schema / schedule_schema 扩展面）
from app.schemas.config_schema import sanitize_config
from app.schemas.schedule_schema import load_update


def _base_config():
    return {
        'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
                 'weekdays': [1, 2, 3, 4, 5, 6, 7], 'randomDelayMax': 5, 'mode': 'normal'},
        'locationId': None,
        'remarks': ['r'],
        'image': {'enabled': False, 'strategy': 'recycle', 'groupId': ''},
        'push': {'channels': []},
        'advanced': {'uaTemplateId': None, 'customUa': ''},
    }


def test_activity_block_normalized_with_defaults():
    ok, cfg = sanitize_config({**_base_config(), 'activity': {'strategy': 'course'}})
    assert ok
    act = cfg['activity']
    assert act['strategy'] == 'course'
    assert act['course']['leadMinutes'] == 60       # 默认值补齐（实测辅导员最早提前 50 分钟发布）
    assert act['course']['tailMinutes'] == 30
    assert act['course']['pollIntervalSec'] == 120
    assert act['course']['excludeCourses'] == []
    assert act['course']['excludeBlocks'] == []     # 块级排除默认为空
    assert act['course']['weekdays'] == []          # 空 = 不限星期
    assert act['fallback'] == {'enabled': True}     # 兜底默认开


def test_activity_block_exclude_blocks_accepted():
    base = _base_config()
    ok, cfg = sanitize_config({**base, 'activity': {
        'strategy': 'course',
        'course': {'excludeBlocks': ['4|移动应用开发技术课程设计|5-8', '7|毕业实习|1-2']},
    }})
    assert ok
    assert cfg['activity']['course']['excludeBlocks'] == [
        '4|移动应用开发技术课程设计|5-8', '7|毕业实习|1-2']


def test_activity_block_rejects_bad_values():
    base = _base_config()
    bad = [
        {'strategy': 'weekly'},                                  # 非法策略
        {'strategy': 'course', 'course': {'leadMinutes': -1}},   # 越界
        {'strategy': 'course', 'course': {'pollIntervalSec': 5}},  # 低于下限 30
        {'strategy': 'course', 'course': {'excludeCourses': '毕业实习'}},  # 应为数组
        {'strategy': 'course', 'course': {'weekdays': [0, 8]}},  # 非法星期
        'course',                                                # 块应为对象
    ]
    for act in bad:
        ok, _ = sanitize_config({**base, 'activity': act})
        assert not ok, f'应拒绝：{act}'


def test_fixed_strategy_kept_without_course_block():
    ok, cfg = sanitize_config({**_base_config(), 'activity': {'strategy': 'fixed'}})
    assert ok
    assert cfg['activity'] == {'strategy': 'fixed'}
    assert 'course' not in cfg['activity']


def test_dorm_config_may_carry_activity_block():
    # 配置套与任务类型解耦：dorm 任务误带 activity 块不报错（调度器不消费）
    ok, cfg = sanitize_config({**_base_config(), 'activity': {'strategy': 'course'}})
    assert ok and 'activity' in cfg


def test_overrides_accept_activity_key():
    ok, data, msg, code = load_update({'overrides': {
        'activity': {'strategy': 'course', 'course': {'leadMinutes': 10},
                     'fallback': {'enabled': False}}}})
    assert ok, msg
    assert data['overrides']['activity']['course']['leadMinutes'] == 10
    assert data['overrides']['activity']['fallback'] == {'enabled': False}
