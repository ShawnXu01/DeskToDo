"""农历与节假日信息。

农历计算（cnlunar）不依赖年份策略数据，长期可用；法定节假日调休信息（chinese_calendar）
按年覆盖，未覆盖的年份会优雅返回 None，而不是报错——对应"今年先用现成数据，
以后随用户自己更新依赖包"的方案。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import cnlunar

try:
    import chinese_calendar
except ImportError:  # pragma: no cover
    chinese_calendar = None


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
        or lunar.get_otherHolidays()
        or lunar.get_otherLunarHolidays()
        or None
    )

    is_holiday: Optional[bool] = None
    if chinese_calendar is not None:
        try:
            is_holiday = chinese_calendar.is_holiday(day)
        except NotImplementedError:
            is_holiday = None

    return DayLunarInfo(lunar_text=lunar_text, festival_text=festival_text, is_statutory_holiday=is_holiday)
