from datetime import date, datetime, time

from deskcal.core.schedule_models import CourseEntry, Term
from deskcal.core.schedule_reminders import find_due_course_reminders


def _term_with_course(*, weekdays=None, start=time(11, 0), end=time(11, 50)) -> Term:
    term = Term.create("Fall - 2026", date(2026, 8, 24), date(2026, 12, 18))
    term.add_course(
        CourseEntry.create(
            code="ECE340",
            title="Semiconductor Electronics",
            location="ECEB 3013",
            weekdays=[3] if weekdays is None else weekdays,
            start_time=start,
            end_time=end,
            color="#F2E6A7",
        )
    )
    return term


def test_course_becomes_due_inside_lead_window():
    reminders = find_due_course_reminders(
        _term_with_course(),
        datetime(2026, 8, 26, 10, 40),
        20,
    )

    assert len(reminders) == 1
    assert reminders[0].title == "20 分钟后上课"
    assert "ECE340 · Semiconductor Electronics" in reminders[0].message
    assert "ECEB 3013" in reminders[0].message


def test_course_is_not_due_before_window_or_after_start():
    term = _term_with_course()

    assert find_due_course_reminders(term, datetime(2026, 8, 26, 10, 39, 59), 20) == []
    assert find_due_course_reminders(term, datetime(2026, 8, 26, 11, 0, 1), 20) == []


def test_unscheduled_wrong_weekday_and_archived_courses_do_not_notify():
    wrong_weekday = _term_with_course(weekdays=[1])
    unscheduled = _term_with_course(weekdays=[], start=None, end=None)
    archived = _term_with_course()
    archived.archived = True
    now = datetime(2026, 8, 26, 10, 45)

    assert find_due_course_reminders(wrong_weekday, now, 20) == []
    assert find_due_course_reminders(unscheduled, now, 20) == []
    assert find_due_course_reminders(archived, now, 20) == []
