import json
from datetime import date, time

import pytest

from deskcal.core.schedule_models import CourseEntry, Term, compute_visible_minutes, split_course_code
from deskcal.core.schedule_import import ScheduleImportError, ScheduleImportRow, analyze_import_rows, parse_schedule_csv
from deskcal.core.schedule_storage import ScheduleStore
from deskcal.ui.schedule.schedule_grid import assign_course_lanes


def _course(code="ECE340", weekdays=None, start=time(11, 0), end=time(11, 50)):
    return CourseEntry.create(
        code=code,
        weekdays=[1, 3, 5] if weekdays is None else weekdays,
        start_time=start,
        end_time=end,
        color="#F2E6A7",
    )


def test_course_validation_and_round_trip():
    course = CourseEntry.create(
        code="ECE340",
        weekdays=[1, 3, 5],
        start_time=time(11, 0),
        end_time=time(11, 50),
        color="#F2E6A7",
        course_resource="https://example.edu/ece340",
    )
    restored = CourseEntry.from_dict(course.to_dict())
    assert restored.code == "ECE340"
    assert restored.weekdays == [1, 3, 5]
    assert restored.start_time == time(11, 0)
    assert restored.course_resource == "https://example.edu/ece340"

    with pytest.raises(ValueError):
        CourseEntry.create(
            code="ECE340",
            weekdays=[],
            start_time=time(11, 0),
            end_time=time(11, 50),
            color="#F2E6A7",
        )
    with pytest.raises(ValueError):
        _course(start=time(12, 0), end=time(11, 0))


def test_unscheduled_course_round_trip_and_visible_range():
    course = CourseEntry.create(
        code="RST230A",
        title="Diversity in RST",
        weekdays=[],
        start_time=None,
        end_time=None,
        color="#F2E6A7",
        notes="ONL · 无固定时间",
    )
    restored = CourseEntry.from_dict(course.to_dict())
    assert restored.weekdays == []
    assert restored.start_time is None
    assert compute_visible_minutes([restored]) == (8 * 60, 18 * 60)


def test_term_validation_and_round_trip():
    term = Term.create("Fall - 2026", date(2026, 8, 24), date(2026, 12, 18))
    term.add_course(_course())
    restored = Term.from_dict(term.to_dict())
    assert restored.name == "Fall - 2026"
    assert restored.courses[0].code == "ECE340"

    with pytest.raises(ValueError):
        Term.create("bad", date(2026, 12, 18), date(2026, 8, 24))


def test_schedule_store_round_trip(tmp_path):
    store = ScheduleStore(tmp_path / "schedule.json")
    term = Term.create("Fall - 2026", date(2026, 8, 24), date(2026, 12, 18))
    term.add_course(_course())
    store.add_term(term)
    store.save()

    raw = json.loads(store.file_path.read_text(encoding="utf-8"))
    assert raw["version"] == 1

    restored = ScheduleStore(store.file_path)
    restored.load()
    assert restored.get_active_term().courses[0].code == "ECE340"


def test_course_resource_is_optional_for_existing_schedule_data():
    raw = _course().to_dict()
    raw.pop("course_resource")

    restored = CourseEntry.from_dict(raw)

    assert restored.course_resource == ""


def test_default_term_selection_and_duplicate(tmp_path):
    store = ScheduleStore(tmp_path / "schedule.json")
    fall = Term.create("Fall - 2026", date(2026, 8, 24), date(2026, 12, 18))
    source_course = _course()
    source_course.course_resource = r"C:\Courses\ECE340\syllabus.pdf"
    fall.add_course(source_course)
    spring = Term.create("Spring - 2027", date(2027, 1, 18), date(2027, 5, 14))
    store.add_term(fall)
    store.add_term(spring)
    store.active_term_id = None

    assert store.choose_default_term(date(2027, 2, 1)) is spring
    duplicate = store.duplicate_term(fall.id, "Fall - 2027")
    assert duplicate.id != fall.id
    assert duplicate.courses[0].id != fall.courses[0].id
    assert duplicate.courses[0].course_resource == source_course.course_resource


def test_course_code_split_and_visible_range():
    assert split_course_code("ECE340") == ("ECE", "340")
    assert split_course_code("CS 101A") == ("CS", "101A")
    assert split_course_code("Graduate Seminar") == ("Graduate Seminar", "")

    courses = [
        _course(start=time(9, 30), end=time(10, 20)),
        _course(code="ECE311", start=time(17, 0), end=time(18, 50)),
    ]
    assert compute_visible_minutes(courses) == (9 * 60, 19 * 60)

    outside_old_limits = [
        _course(start=time(5, 15), end=time(6, 0)),
        _course(code="ECE311", start=time(22, 0), end=time(23, 30)),
    ]
    assert compute_visible_minutes(outside_old_limits) == (5 * 60, 24 * 60)


def test_overlapping_courses_share_lanes_without_narrowing_later_courses():
    first = _course(code="ECE340", start=time(9, 0), end=time(10, 0))
    overlap = _course(code="CS101", start=time(9, 30), end=time(10, 30))
    later = _course(code="MATH241", start=time(11, 0), end=time(12, 0))

    lanes = assign_course_lanes([first, overlap, later])

    assert lanes[first.id][1] == 2
    assert lanes[overlap.id][1] == 2
    assert lanes[later.id] == (0, 1)


def test_schedule_csv_import_supports_scheduled_and_unscheduled_courses(tmp_path):
    file_path = tmp_path / "schedule.csv"
    file_path.write_text(
        "course_code,course_title,instructor,location,weekdays,start_time,end_time,notes\n"
        'ECE 329 E,Fields and Waves I,"Gong, Songbin",ECEB 1015,1|3|5,13:00,13:50,DIS\n'
        "RST 230 A,Diversity in RST,Stodolska Monika,ONL,,,,Second Half · 无固定时间\n",
        encoding="utf-8-sig",
    )

    rows = parse_schedule_csv(file_path)

    assert rows[0].weekdays == [1, 3, 5]
    assert rows[0].start_time == time(13, 0)
    assert rows[0].instructor == "Gong, Songbin"
    assert rows[1].is_unscheduled
    assert rows[1].location == "ONL"


def test_schedule_csv_import_reports_invalid_rows(tmp_path):
    file_path = tmp_path / "bad.csv"
    file_path.write_text(
        "course_code,course_title,instructor,location,weekdays,start_time,end_time,notes\n"
        "ECE340,Semiconductor Electronics,,ECEB 3013,Mon|Wed,11:00,10:50,\n",
        encoding="utf-8",
    )

    with pytest.raises(ScheduleImportError) as exc_info:
        parse_schedule_csv(file_path)

    assert "ISO 星期数字" in str(exc_info.value)
    assert "end_time 必须晚于" in str(exc_info.value)


def test_schedule_csv_import_rejects_unquoted_commas(tmp_path):
    file_path = tmp_path / "extra-column.csv"
    file_path.write_text(
        "course_code,course_title,instructor,location,weekdays,start_time,end_time,notes\n"
        "ECE329,Fields and Waves,Gong, Songbin,ECEB 1015,1|3|5,13:00,13:50,DIS\n",
        encoding="utf-8",
    )

    with pytest.raises(ScheduleImportError, match="未加引号的逗号"):
        parse_schedule_csv(file_path)


def test_schedule_import_analysis_reports_missing_duplicate_and_conflict():
    existing = _course(code="ECE340", weekdays=[1], start=time(11, 0), end=time(11, 50))
    rows = [
        ScheduleImportRow("ECE340", "", "", "", [1], time(11, 0), time(11, 50), ""),
        ScheduleImportRow("CS101", "Intro", "Smith", "Room 1", [1], time(11, 30), time(12, 20), ""),
    ]

    issues = analyze_import_rows(rows, [existing])

    assert "缺少课程名称、地点、教师" in issues[0]
    assert "与现有课程重复" in issues[0]
    assert "与 ECE340 时间冲突" in issues[1]
    assert "与导入行 3 时间冲突" in issues[0]
