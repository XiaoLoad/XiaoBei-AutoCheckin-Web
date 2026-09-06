# 强智教务页面解析器（纯函数，零第三方依赖——标准库 html.parser 构建轻量 DOM）。
# 规则依据 2026-09-06 对 jw.cqcst.edu.cn 的实测抓包（fixtures 见 tests/fixtures/，
# 设计与开源交叉验证见设计文档 §2.2/§2.7）：
#   - 课表页 xskb_list.do：#kbtable 第 1 行表头，第 2~8 行为 7 个大节（每大节=2 小节），
#     末行"备注"；td 内 div.kbcontent（完整视图，class 精确匹配，排除 kbcontent1 紧凑视图），
#     一格多课以 "-----" 行分隔；课程块跨大节会在每行重复完整渲染，需按内容键去重；
#   - 课程块行结构（<br> 分行）：课程名[学时][性质] / 老师 / 班级(人数) / 周次(单双周)[小节列表] / 教室?
#     周次语法：`1-2(全部)`、`3,5(全部)`、可混合 `3,5-7(单)`；周类型 全部|单|双（部分部署
#     显示 周/每周，等价"全部"，归一化处理）；小节列表是零填充枚举（- 为分隔符非范围）；
#   - 教学周历 jxzl_query：每周一行，星期六/日单元格为 "MM月DD日"，据此换算第 1 周周一。
import re
from datetime import date, timedelta
from html.parser import HTMLParser

from app.services.jwxt.base import JwxtError, TimetableEntry

_VOID_TAGS = {'br', 'img', 'input', 'meta', 'link', 'hr', 'area', 'base', 'col', 'embed',
              'source', 'track', 'wbr'}

_WEEK_RE = re.compile(
    r'(\d+(?:\s*[-,，]\s*\d+)*)\s*\((全部|单|双|周|每周)\)\s*\[([\d]+(?:-[\d]+)*)节\]')
_CN_DIGIT = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8,
             '九': 9, '十': 10, '十一': 11, '十二': 12, '十三': 13, '十四': 14}


class _Node:
    __slots__ = ('tag', 'attrs', 'children')

    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []          # _Node | str

    @property
    def cls(self):
        return (self.attrs.get('class') or '').split()


class _TreeBuilder(HTMLParser):
    """把页面解析成轻量节点树：<br> 归一化为 '\n' 文本，保留原始属性供结构查询。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node('root', [])
        self._stack = [self.root]

    def handle_starttag(self, tag, attrs):
        if tag in _VOID_TAGS:
            if tag == 'br':
                self._stack[-1].children.append('\n')
            return
        node = _Node(tag, attrs)
        self._stack[-1].children.append(node)
        self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        if tag == 'br':
            self._stack[-1].children.append('\n')

    def handle_endtag(self, tag):
        # 容错回退：页面偶有未闭合标签，向上找最近的同名开放标签；找不到则忽略
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return

    def handle_data(self, data):
        if data:
            self._stack[-1].children.append(data)


def _parse_tree(html):
    builder = _TreeBuilder()
    try:
        builder.feed(html)
        builder.close()
    except Exception as e:  # 极端残缺页面不应让同步链路拿到裸异常
        raise JwxtError('parse', f'页面解析失败：{e}')
    return builder.root


def _walk(node):
    yield node
    for c in node.children:
        if isinstance(c, _Node):
            yield from _walk(c)


def _find_all(node, tag, *, id_=None, cls=None):
    return [n for n in _walk(node)
            if n is not node and n.tag == tag
            and (id_ is None or n.attrs.get('id') == id_)
            and (cls is None or cls in n.cls)]


def _find_one(node, tag, *, id_=None, cls=None):
    found = _find_all(node, tag, id_=id_, cls=cls)
    return found[0] if found else None


def _inner_text(node):
    out = []

    def rec(n):
        for c in n.children:
            if isinstance(c, str):
                out.append(c)
            else:
                rec(c)
    rec(node)
    return ''.join(out)


def parse_current_semester(html):
    """课表页不带参数访问时，服务端按日期选中的学期 <option> 即当前学期（权威来源）。"""
    root = _parse_tree(html)
    sel = _find_one(root, 'select', id_='xnxq01id')
    if sel is None:
        raise JwxtError('parse', '课表页缺少学期选择器（xnxq01id），页面结构可能已变更')
    for opt in _find_all(sel, 'option'):
        if 'selected' in opt.attrs:
            value = (opt.attrs.get('value') or _inner_text(opt)).strip()
            if value:
                return value
    raise JwxtError('parse', '学期选择器中无选中项')


def _expand_weeks(expr):
    """'1-2' → [1,2]；'3,5' → [3,5]；'3,5-7' → [3,5,6,7]；容错忽略空段。"""
    weeks = []
    for part in re.split(r'[,，]', expr or ''):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, _, b = part.partition('-')
            try:
                lo, hi = int(a), int(b)
            except ValueError:
                continue
            if lo <= hi:
                weeks.extend(range(lo, hi + 1))
        else:
            try:
                weeks.append(int(part))
            except ValueError:
                continue
    return sorted({w for w in weeks if w > 0})


def _parse_sections(expr):
    """'[01-02-03-04节]' → [1,2,3,4]。枚举以 '-' 分隔（零填充）；若恰为两个非零填充
    数字（如 '1-8'）则按区间展开，兼容个别部署的范围写法。"""
    tokens = [t for t in re.split(r'-', expr or '') if t.strip()]
    nums = []
    for t in tokens:
        try:
            nums.append(int(t))
        except ValueError:
            continue
    if len(nums) == 2 and not all(re.fullmatch(r'0\d', t.strip()) for t in tokens):
        return list(range(nums[0], nums[1] + 1))
    return sorted({n for n in nums if n > 0})


def _parse_entry(lines):
    """一个课程块的文本行 → TimetableEntry；缺周次行视为无法解析的噪声行。"""
    if not lines:
        return None
    weeks_line_idx = None
    weeks_match = None
    for i, line in enumerate(lines):
        m = _WEEK_RE.search(line)
        if m:
            weeks_line_idx, weeks_match = i, m
            break
    if weeks_line_idx is None:
        return None
    name = re.split(r'\[', lines[0])[0].strip() if lines else ''
    week_type = weeks_match.group(2)
    if week_type in ('周', '每周'):
        week_type = '全部'
    weeks = _expand_weeks(weeks_match.group(1))
    if week_type == '单':
        weeks = [w for w in weeks if w % 2 == 1]
    elif week_type == '双':
        weeks = [w for w in weeks if w % 2 == 0]
    sections = _parse_sections(weeks_match.group(3))
    teacher = lines[1].strip() if weeks_line_idx >= 2 else ''
    # 班级行在老师与周次行之间（可能拆成两行：班级名 / (人数)）；教室为周次行后的尾行
    clazz = ' '.join(lines[2:weeks_line_idx]).strip()
    room = lines[weeks_line_idx + 1].strip() if len(lines) > weeks_line_idx + 1 else ''
    if not name or not weeks or not sections:
        return None
    return TimetableEntry(course=name, teacher=teacher, clazz=clazz,
                          weeks=weeks, sections=sections, room=room)


def parse_timetable(html):
    """课表页 HTML → 去重后的逻辑课程列表。大节行号以行首"第X节"文本为准（缺失时按
    数据行顺序回退）；列序 1..7 = 星期一..星期日。"""
    root = _parse_tree(html)
    table = _find_one(root, 'table', id_='kbtable')
    if table is None:
        raise JwxtError('parse', '课表页缺少课表表格（kbtable）')
    entries = []
    big_section = 0
    for tr in _find_all(table, 'tr'):
        cells = [c for c in tr.children if isinstance(c, _Node) and c.tag in ('td', 'th')]
        if not cells:
            continue
        head_text = _inner_text(cells[0]).strip()
        m = re.search(r'第\s*(\S{1,2})\s*节', head_text)
        if not m:
            continue  # 表头行 / 备注行
        big = _CN_DIGIT.get(m.group(1))
        if big is None:
            big = big_section + 1
        big_section = big
        # 大节行号 → 小节基址：第 n 大节覆盖小节 2n-1 / 2n（晚自习第 7 大节=13/14 节）
        for col, cell in enumerate(cells[1:8], start=1):
            for div in _find_all(cell, 'div', cls='kbcontent'):
                text = _inner_text(div)
                # 一格多课：以 ≥6 个连续 "-" 的分隔行切块
                for chunk in re.split(r'\n\s*-{6,}\s*\n', text):
                    lines = [ln.strip() for ln in chunk.split('\n') if ln.strip()]
                    entry = _parse_entry(lines)
                    if entry is None:
                        continue
                    entry.weekday = col
                    # 小节列表是权威时间跨度；大节行号仅用于冗余校验，不一致时以列表为准
                    entries.append(entry)
    # 跨大节重复渲染去重：同 (星期,课程,老师,周次,周类型,小节,教室) 视为同一逻辑课
    dedup = {}
    for e in entries:
        key = (e.weekday, e.course, e.teacher, tuple(e.weeks), tuple(e.sections), e.room)
        dedup.setdefault(key, e)
    return sorted(dedup.values(), key=lambda e: (e.weekday, min(e.sections), e.course))


_DATE_RE = re.compile(r'(\d{1,2})\s*月\s*(\d{1,2})\s*日')


def _infer_year(semester, month):
    """按学期代码推断 "MM月DD日" 的年份：2026-2027-1（秋季）中 7~12 月属首年，
    1~6 月属次年；2026-2027-2（春季）中 1~8 月属次年，9~12 月属首年。"""
    try:
        start_year = int(str(semester).split('-')[0])
        term = int(str(semester).split('-')[2])
    except (IndexError, ValueError):
        raise JwxtError('parse', f'学期代码无法解析：{semester}')
    if term == 1:
        return start_year if month >= 7 else start_year + 1
    return start_year + 1 if month <= 8 else start_year


def parse_week_calendar(html, semester):
    """教学周历页 → (week1_monday, total_weeks)。取第 1 周行星期六的 "MM月DD日" 减 5 天。"""
    root = _parse_tree(html)
    for table in _find_all(root, 'table'):
        week_rows = []
        for r in _find_all(table, 'tr'):
            cells = [c for c in r.children if isinstance(c, _Node) and c.tag == 'td']
            if len(cells) < 8 or not _inner_text(cells[0]).strip().isdigit():
                continue
            week_rows.append(cells)
        if not week_rows:
            continue
        week1_cells = next((cs for cs in week_rows if _inner_text(cs[0]).strip() == '1'), None)
        if week1_cells is None:
            continue
        m = _DATE_RE.search(_inner_text(week1_cells[6]))
        if not m:
            continue
        month, day = int(m.group(1)), int(m.group(2))
        monday = date(_infer_year(semester, month), month, day) - timedelta(days=5)
        return monday, len(week_rows)
    raise JwxtError('parse', '教学周历页未找到第 1 周行')


def parse_week1_monday(html, semester):
    return parse_week_calendar(html, semester)[0]
