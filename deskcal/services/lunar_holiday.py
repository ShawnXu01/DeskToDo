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
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import cnlunar

from deskcal.core.storage import get_data_dir

try:
    import chinese_calendar
except ImportError:  # pragma: no cover
    chinese_calendar = None

HOLIDAYS_FILE_NAME = "holidays.json"
_DEFAULT_HOLIDAYS_ASSET = Path(__file__).resolve().parent.parent / "assets" / "holidays_2026_default.json"

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


def get_formula_holiday(day: date) -> Optional[str]:
    """每年日期不固定、按公式计算的特殊日期（非法定节假日，不需要导入）。"""
    if day == _nth_weekday_of_month(day.year, 5, 6, 2):
        return "母亲节"
    if day == _nth_weekday_of_month(day.year, 6, 6, 3):
        return "父亲节"
    if day == _nth_weekday_of_month(day.year, 11, 3, 4):
        return "感恩节"
    return None


def get_holidays_file() -> Path:
    return get_data_dir() / HOLIDAYS_FILE_NAME


def ensure_default_holidays_seeded() -> None:
    """首次运行时把内置的当年法定节假日默认数据复制到用户数据目录，之后用户可自行替换导入。"""
    target = get_holidays_file()
    if not target.exists() and _DEFAULT_HOLIDAYS_ASSET.exists():
        shutil.copy(_DEFAULT_HOLIDAYS_ASSET, target)


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
    """优先显示导入的法定节假日名，否则显示公式计算的特殊日期（母亲节/父亲节等）。"""
    imported = load_imported_holidays()
    if day in imported:
        return imported[day]
    return get_formula_holiday(day)


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
