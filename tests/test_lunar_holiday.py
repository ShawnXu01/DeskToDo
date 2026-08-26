"""美国重要日期的固定日期、公式日期和年度导入数据。"""
import json
from datetime import date
from pathlib import Path

from deskcal.services import lunar_holiday
from deskcal.services.lunar_holiday import get_day_lunar_info, get_formula_holiday, get_special_day_label


def test_us_federal_formula_holidays_for_2026():
    assert get_formula_holiday(date(2026, 1, 19)) == "马丁·路德·金纪念日"
    assert get_formula_holiday(date(2026, 2, 16)) == "总统日（华盛顿诞辰）"
    assert get_formula_holiday(date(2026, 5, 25)) == "阵亡将士纪念日"
    assert get_formula_holiday(date(2026, 9, 7)) == "劳动节（美国）"
    assert get_formula_holiday(date(2026, 10, 12)) == "原住民日/哥伦布日"
    assert get_formula_holiday(date(2026, 11, 26)) == "感恩节"


def test_us_calendar_and_shopping_dates_for_2026():
    assert get_formula_holiday(date(2026, 3, 8)) == "美国夏令时开始"
    assert get_formula_holiday(date(2026, 4, 3)) == "耶稣受难日"
    assert get_formula_holiday(date(2026, 4, 5)) == "复活节"
    assert get_formula_holiday(date(2026, 11, 1)) == "美国夏令时结束"
    assert get_formula_holiday(date(2026, 11, 3)) == "美国选举日"
    assert get_formula_holiday(date(2026, 11, 27)) == "黑色星期五"
    assert get_formula_holiday(date(2026, 11, 30)) == "网络星期一"


def test_formula_dates_continue_to_work_in_future_years():
    assert get_formula_holiday(date(2027, 3, 28)) == "复活节"
    assert get_formula_holiday(date(2028, 11, 7)) == "美国选举日"
    assert get_formula_holiday(date(2030, 4, 21)) == "复活节"
    assert get_formula_holiday(date(2031, 11, 27)) == "感恩节"
    assert get_formula_holiday(date(2031, 11, 28)) == "黑色星期五"


def test_fixed_us_dates_are_in_existing_solar_holiday_path():
    assert get_day_lunar_info(date(2026, 7, 4)).festival_text == "美国独立日"
    assert get_day_lunar_info(date(2026, 11, 11)).festival_text == "退伍军人节"


def test_imported_chinese_holiday_and_us_date_are_combined(tmp_path, monkeypatch):
    holidays_file = tmp_path / "holidays.json"
    holidays_file.write_text('{"2026-06-19": "端午节"}', encoding="utf-8")
    monkeypatch.setattr(lunar_holiday, "get_holidays_file", lambda: holidays_file)

    assert get_special_day_label(date(2026, 6, 19)) == "端午节 / 六月节"


def test_us_fixed_holiday_weekend_observation():
    assert get_formula_holiday(date(2026, 7, 3)) == "美国独立日（调休）"
    assert get_formula_holiday(date(2027, 6, 18)) == "六月节（调休）"
    assert get_formula_holiday(date(2027, 12, 31)) == "美国元旦（调休）"


def test_2026_tax_deadline_uses_shared_annual_import_file():
    asset = Path(__file__).resolve().parents[1] / "deskcal" / "assets" / "holidays_2026_default.json"
    data = json.loads(asset.read_text(encoding="utf-8"))
    assert data["2026-04-15"] == "美国报税截止日"


def test_existing_holiday_file_gets_new_annual_date_without_overwrite(tmp_path, monkeypatch):
    holidays_file = tmp_path / "holidays.json"
    holidays_file.write_text(
        '{"2026-04-15": "我的报税提醒", "2026-05-01": "劳动节"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(lunar_holiday, "get_holidays_file", lambda: holidays_file)

    lunar_holiday.ensure_default_holidays_seeded()

    data = json.loads(holidays_file.read_text(encoding="utf-8"))
    assert data["2026-04-15"] == "我的报税提醒"
    assert data["2026-05-01"] == "劳动节"


def test_existing_holiday_file_gets_missing_annual_date(tmp_path, monkeypatch):
    holidays_file = tmp_path / "holidays.json"
    holidays_file.write_text('{"2026-05-01": "劳动节"}', encoding="utf-8")
    monkeypatch.setattr(lunar_holiday, "get_holidays_file", lambda: holidays_file)

    lunar_holiday.ensure_default_holidays_seeded()

    data = json.loads(holidays_file.read_text(encoding="utf-8"))
    assert data["2026-04-15"] == "美国报税截止日"
