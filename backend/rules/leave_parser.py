"""请假时间兜底解析（FR-006，需求 11.2）。

支持：今天/明天/后天、明确日期（2026-11-21 / 11月21日）、
半天/一天/三天及中文数字。解析失败回退默认（今天 09:00-18:00）。
"""
import re
from datetime import datetime, timedelta

_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_FMT = "%Y-%m-%d %H:%M:%S"


def _parse_days(text):
    if "半天" in text:
        return 0.5
    m = re.search(r"([0-9]+|[一二两三四五六七八九十])\s*天", text)
    if m:
        token = m.group(1)
        return _CN_NUM.get(token, None) if not token.isdigit() else int(token)
    return None


def parse_leave_time(reason: str, now: datetime = None):
    """返回 (start_time, end_time, parsed)。parsed=False 表示使用了默认回退。"""
    now = now or datetime.now()
    reason = reason or ""
    start_date = None
    parsed = False

    # 相对日期
    if "后天" in reason:
        start_date, parsed = now.date() + timedelta(days=2), True
    elif "明天" in reason:
        start_date, parsed = now.date() + timedelta(days=1), True
    elif "今天" in reason:
        start_date, parsed = now.date(), True

    # 明确日期：2026-11-21 / 2026/11/21
    if start_date is None:
        m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", reason)
        if m:
            try:
                start_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
                parsed = True
            except ValueError:
                pass
    # 明确日期：11月21日（当年）
    if start_date is None:
        m = re.search(r"(\d{1,2})月(\d{1,2})[日号]", reason)
        if m:
            try:
                start_date = datetime(now.year, int(m.group(1)), int(m.group(2))).date()
                parsed = True
            except ValueError:
                pass

    days = _parse_days(reason)
    if days is not None:
        parsed = True
    if start_date is None:
        start_date = now.date()  # 默认回退：今天

    start = datetime.combine(start_date, datetime.min.time().replace(hour=9))
    if days == 0.5:
        end = datetime.combine(start_date, datetime.min.time().replace(hour=12))
    elif days and days >= 1:
        end = datetime.combine(start_date + timedelta(days=int(days) - 1),
                               datetime.min.time().replace(hour=18))
    else:
        end = datetime.combine(start_date, datetime.min.time().replace(hour=18))
    return start.strftime(_FMT), end.strftime(_FMT), parsed