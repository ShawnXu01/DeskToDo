"""课表数据模型：学期（Term）和扁平课程条目（CourseEntry）。"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Optional


@dataclass
class CourseEntry:
    id: str
    code: str
    title: str
    instructor: str
    location: str
    weekdays: list[int]
    start_time: Optional[time]
    end_time: Optional[time]
    color: str
    notes: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.code = self.code.strip()
        if not self.code:
            raise ValueError("课程代码不能为空")
        if any(day < 1 or day > 7 for day in self.weekdays):
            raise ValueError("weekdays 取值必须是 1(周一)~7(周日)")
        self.weekdays = sorted(set(self.weekdays))
        has_days = bool(self.weekdays)
        has_start = self.start_time is not None
        has_end = self.end_time is not None
        if has_days != has_start or has_start != has_end:
            raise ValueError("固定时间课程必须同时填写上课日、开始时间和结束时间")
        if has_start and self.start_time >= self.end_time:
            raise ValueError("课程结束时间必须晚于开始时间")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", self.color):
            raise ValueError("课程颜色必须是 #RRGGBB 格式")

    @classmethod
    def create(
        cls,
        *,
        code: str,
        weekdays: list[int],
        start_time: Optional[time],
        end_time: Optional[time],
        color: str,
        title: str = "",
        instructor: str = "",
        location: str = "",
        notes: str = "",
    ) -> "CourseEntry":
        now = datetime.now()
        return cls(
            id=str(uuid.uuid4()),
            code=code,
            title=title.strip(),
            instructor=instructor.strip(),
            location=location.strip(),
            weekdays=weekdays,
            start_time=start_time,
            end_time=end_time,
            color=color,
            notes=notes.strip(),
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "title": self.title,
            "instructor": self.instructor,
            "location": self.location,
            "weekdays": self.weekdays,
            "start_time": self.start_time.strftime("%H:%M") if self.start_time else None,
            "end_time": self.end_time.strftime("%H:%M") if self.end_time else None,
            "color": self.color,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CourseEntry":
        return cls(
            id=data["id"],
            code=data["code"],
            title=data.get("title", ""),
            instructor=data.get("instructor", ""),
            location=data.get("location", ""),
            weekdays=list(data["weekdays"]),
            start_time=time.fromisoformat(data["start_time"]) if data.get("start_time") else None,
            end_time=time.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            color=data["color"],
            notes=data.get("notes", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


@dataclass
class Term:
    id: str
    name: str
    start_date: date
    end_date: date
    archived: bool
    created_at: datetime
    updated_at: datetime
    courses: list[CourseEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("学期名称不能为空")
        if self.start_date > self.end_date:
            raise ValueError("学期结束日期不能早于开始日期")

    @classmethod
    def create(cls, name: str, start_date: date, end_date: date) -> "Term":
        now = datetime.now()
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            start_date=start_date,
            end_date=end_date,
            archived=False,
            created_at=now,
            updated_at=now,
        )

    def add_course(self, course: CourseEntry) -> None:
        self.courses.append(course)
        self.updated_at = datetime.now()

    def get_course(self, course_id: str) -> Optional[CourseEntry]:
        return next((course for course in self.courses if course.id == course_id), None)

    def remove_course(self, course_id: str) -> None:
        before = len(self.courses)
        self.courses = [course for course in self.courses if course.id != course_id]
        if len(self.courses) == before:
            raise KeyError(f"课程不存在: {course_id}")
        self.updated_at = datetime.now()

    def sorted_courses(self) -> list[CourseEntry]:
        return sorted(
            self.courses,
            key=lambda course: (course.start_time is None, course.start_time or time.max, course.code.casefold()),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "archived": self.archived,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "courses": [course.to_dict() for course in self.courses],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Term":
        return cls(
            id=data["id"],
            name=data["name"],
            start_date=date.fromisoformat(data["start_date"]),
            end_date=date.fromisoformat(data["end_date"]),
            archived=data.get("archived", False),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            courses=[CourseEntry.from_dict(item) for item in data.get("courses", [])],
        )


def split_course_code(code: str) -> tuple[str, str]:
    """把 ECE340 / CS 101A 拆成两行；无法可靠拆分时第二行留空。"""
    normalized = " ".join(code.strip().split())
    match = re.fullmatch(r"([A-Za-z]+)\s*([0-9]+[A-Za-z]?)", normalized)
    if match:
        return match.group(1).upper(), match.group(2).upper()
    return normalized, ""


def minutes_since_midnight(value: time) -> int:
    return value.hour * 60 + value.minute


def compute_visible_minutes(courses: list[CourseEntry]) -> tuple[int, int]:
    """自动时间范围：从最早课程所在整点到最晚课程结束后的最近整点。"""
    scheduled = [course for course in courses if course.start_time is not None and course.end_time is not None]
    if not scheduled:
        return 8 * 60, 18 * 60
    earliest = min(minutes_since_midnight(course.start_time) for course in scheduled)
    latest = max(minutes_since_midnight(course.end_time) for course in scheduled)
    start = earliest // 60 * 60
    end = ((latest + 59) // 60) * 60
    return start, end
