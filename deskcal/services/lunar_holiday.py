"""农历与节假日信息。

农历计算（cnlunar）不依赖年份策略数据，长期可用；法定节假日调休信息（chinese_calendar）
按年覆盖，未覆盖的年份会优雅返回 None，而不是报错——对应"今年先用现成数据，
以后随用户自己更新依赖包"的方案。
"""
from __future__ import annotations

import calendar
import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import cnlunar

from deskcal.core.storage import atomic_write_json, get_data_dir

try:
    import chinese_calendar
except ImportError:  # pragma: no cover
    chinese_calendar = None

HOLIDAYS_FILE_NAME = "holidays.json"
_DEFAULT_HOLIDAYS_ASSET = Path(__file__).resolve().parent.parent / "assets" / "holidays_2026_default.json"

# 已安装过旧版本的用户已经有 holidays.json，启动时只补这些后来新增的年度日期；
# setdefault 保证不会覆盖用户自己导入或修改过的同日名称。
_ANNUAL_HOLIDAY_ADDITIONS = {
    "2026-04-15": "美国报税截止日",
}

# 美国固定日期的重要节日单独保留一份，遇到中国年度节假日撞日时可以合并显示。
_US_FIXED_IMPORTANT_DATES: dict[tuple[int, int], str] = {
    (3, 17): "圣帕特里克节",
    (6, 19): "六月节",
    (7, 4): "美国独立日",
    (9, 11): "爱国者日（美国）",
    (11, 11): "退伍军人节",
}

# 公历固定日期的节日：大众国际节日 + 世界性纪念日（联合国/国际组织认定），
# 替代 cnlunar 内置 otherHolidaysList 里那些中国政治人物纪念日和民间神诞日。
_SOLAR_CURATED_HOLIDAYS: dict[tuple[int, int], str] = {
    (2, 14): "情人节",
    (2, 21): "国际母语日",
    (3, 8): "国际妇女节",
    (3, 22): "世界水日",
    (4, 1): "愚人节",
    (4, 7): "世界卫生日",
    (4, 22): "世界地球日",
    (6, 1): "儿童节",
    (6, 5): "世界环境日",
    (7, 20): "登月纪念日",
    (9, 21): "国际和平日",
    (10, 24): "联合国日",
    (10, 31): "万圣节",
    (12, 1): "世界艾滋病日",
    (12, 10): "世界人权日",
    (12, 24): "平安夜",
    (12, 25): "圣诞节",
    **_US_FIXED_IMPORTANT_DATES,
}

# 农历固定日期的中国传统节日（非法定，法定节假日走 holidays.json 导入）。
_LUNAR_CURATED_HOLIDAYS: dict[tuple[int, int], str] = {
    (1, 15): "元宵节",
    (2, 2): "龙抬头",
    (7, 7): "七夕",
    (7, 15): "中元节",
    (9, 9): "重阳节",
    (12, 8): "腊八节",
    (12, 23): "小年",
    (12, 30): "除夕",
}


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """weekday: 0=周一...6=周日；n: 第几个（从1开始）。"""
    cal = calendar.Calendar()
    matches = [d for d in cal.itermonthdates(year, month) if d.month == month and d.weekday() == weekday]
    return matches[n - 1]


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """weekday: 0=周一...6=周日；返回当月最后一个指定星期。"""
    cal = calendar.Calendar()
    matches = [d for d in cal.itermonthdates(year, month) if d.month == month and d.weekday() == weekday]
    return matches[-1]


def _easter_sunday(year: int) -> date:
    """计算西方教会复活节日期（Gregorian computus）。"""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    weekday_offset = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * weekday_offset) // 451
    month = (h + weekday_offset - 7 * m + 114) // 31
    day = (h + weekday_offset - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _observed_us_fixed_holiday(day: date) -> Optional[str]:
    """美国固定日期联邦节日落在周末时，返回相邻工作日的调休名称。"""
    fixed_holidays = {
        date(day.year, 1, 1): "美国元旦",
        date(day.year, 6, 19): "六月节",
        date(day.year, 7, 4): "美国独立日",
        date(day.year, 11, 11): "退伍军人节",
        date(day.year, 12, 25): "圣诞节",
    }
    # 元旦的调休可能落在上一年 12 月 31 日，需同时检查下一年的元旦。
    fixed_holidays[date(day.year + 1, 1, 1)] = "美国元旦"
    for holiday, name in fixed_holidays.items():
        if holiday.weekday() == 5 and day == holiday - timedelta(days=1):
            return f"{name}（调休）"
        if holiday.weekday() == 6 and day == holiday + timedelta(days=1):
            return f"{name}（调休）"
    return None


def get_formula_holiday(day: date) -> Optional[str]:
    """按稳定规则计算、不需要年度导入的节日和重要日期。"""
    observed_holiday = _observed_us_fixed_holiday(day)
    if observed_holiday:
        return observed_holiday
    if day == _nth_weekday_of_month(day.year, 1, 0, 3):
        return "马丁·路德·金纪念日"
    if day == _nth_weekday_of_month(day.year, 2, 0, 3):
        return "总统日（华盛顿诞辰）"
    if day == _nth_weekday_of_month(day.year, 3, 6, 2):
        return "美国夏令时开始"
    easter = _easter_sunday(day.year)
    if day == easter - timedelta(days=2):
        return "耶稣受难日"
    if day == easter:
        return "复活节"
    if day == _nth_weekday_of_month(day.year, 5, 6, 2):
        return "母亲节"
    if day == _last_weekday_of_month(day.year, 5, 0):
        return "阵亡将士纪念日"
    if day == _nth_weekday_of_month(day.year, 6, 6, 3):
        return "父亲节"
    if day == _nth_weekday_of_month(day.year, 9, 0, 1):
        return "劳动节（美国）"
    if day == _nth_weekday_of_month(day.year, 10, 0, 2):
        return "原住民日/哥伦布日"
    if day == _nth_weekday_of_month(day.year, 11, 6, 1):
        return "美国夏令时结束"
    if day == _nth_weekday_of_month(day.year, 11, 0, 1) + timedelta(days=1):
        return "美国选举日"
    if day == _nth_weekday_of_month(day.year, 11, 3, 4):
        return "感恩节"
    if day == _nth_weekday_of_month(day.year, 11, 3, 4) + timedelta(days=1):
        return "黑色星期五"
    if day == _nth_weekday_of_month(day.year, 11, 3, 4) + timedelta(days=4):
        return "网络星期一"
    return None


def get_holidays_file() -> Path:
    return get_data_dir() / HOLIDAYS_FILE_NAME


def ensure_default_holidays_seeded() -> None:
    """种入年度节假日，并为旧版已有文件补充新增日期，不覆盖用户现有内容。"""
    target = get_holidays_file()
    if not target.exists() and _DEFAULT_HOLIDAYS_ASSET.exists():
        shutil.copy(_DEFAULT_HOLIDAYS_ASSET, target)
        return

    if not target.exists():
        return
    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return
    except (json.JSONDecodeError, OSError):
        return

    original_count = len(data)
    for day, label in _ANNUAL_HOLIDAY_ADDITIONS.items():
        data.setdefault(day, label)
    if len(data) != original_count:
        atomic_write_json(target, data)


def load_imported_holidays() -> dict[date, str]:
    """读取用户导入/默认种入的法定节假日文件，格式 {"2026-05-01": "劳动节", ...}。
    文件不存在或格式有问题时静默返回空字典，不抛异常、不弹窗。
    """
    path = get_holidays_file()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        result: dict[date, str] = {}
        for key, value in raw.items():
            try:
                result[date.fromisoformat(key)] = str(value)
            except ValueError:
                continue
        return result
    except (json.JSONDecodeError, OSError):
        return {}


def get_special_day_label(day: date) -> Optional[str]:
    """合并年度导入、公式日期和美国固定重要日期，同一天的多个名称不会互相遮盖。"""
    imported = load_imported_holidays()
    labels = [
        imported.get(day),
        get_formula_holiday(day),
        _US_FIXED_IMPORTANT_DATES.get((day.month, day.day)),
    ]
    unique_labels = list(dict.fromkeys(label for label in labels if label))
    return " / ".join(unique_labels) or None


@dataclass
class DayLunarInfo:
    lunar_text: str
    festival_text: Optional[str]
    is_statutory_holiday: Optional[bool]


def get_day_lunar_info(day: date) -> DayLunarInfo:
    lunar = cnlunar.Lunar(datetime(day.year, day.month, day.day), godType="8char")

    if lunar.lunarDay == 1:
        lunar_text = lunar.lunarMonthCn.rstrip("大小")
    else:
        lunar_text = lunar.lunarDayCn

    festival_text = (
        lunar.get_legalHolidays()
        or _SOLAR_CURATED_HOLIDAYS.get((day.month, day.day))
        or _LUNAR_CURATED_HOLIDAYS.get((lunar.lunarMonth, lunar.lunarDay))
        or None
    )

    is_holiday: Optional[bool] = None
    if chinese_calendar is not None:
        try:
            is_holiday = chinese_calendar.is_holiday(day)
        except NotImplementedError:
            is_holiday = None

    return DayLunarInfo(lunar_text=lunar_text, festival_text=festival_text, is_statutory_holiday=is_holiday)
