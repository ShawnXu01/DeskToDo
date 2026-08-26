"""课前提醒的纯计算逻辑。"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from deskcal.core.schedule_models import Term


@dataclass(frozen=True)
class CourseReminder:
    key: str
    title: str
    message: str


def find_due_course_reminders(term: Term | None, now: datetime, lead_minutes: int) -> list[CourseReminder]:
    if (
        term is None
        or term.archived
        or not term.start_date <= now.date() <= term.end_date
        or lead_minutes < 1
    ):
        return []

    reminders: list[CourseReminder] = []
    for course in term.sorted_courses():
        if course.start_time is None or course.end_time is None or now.isoweekday() not in course.weekdays:
            continue

        starts_at = datetime.combine(now.date(), course.start_time)
        seconds_until_start = (starts_at - now).total_seconds()
        if seconds_until_start < 0 or seconds_until_start > lead_minutes * 60:
            continue

        minutes_until_start = max(0, math.ceil(seconds_until_start / 60))
        title = "课程即将开始" if minutes_until_start == 0 else f"{minutes_until_start} 分钟后上课"
        course_name = f"{course.code} · {course.title}" if course.title else course.code
        time_range = f"{course.start_time.strftime('%H:%M')}–{course.end_time.strftime('%H:%M')}"
        details = f"{course_name}\n{time_range}"
        if course.location:
            details += f" · {course.location}"
        reminders.append(
            CourseReminder(
                key=f"{now.date().isoformat()}:{term.id}:{course.id}:{course.start_time.isoformat()}",
                title=title,
                message=details,
            )
        )
    return reminders
