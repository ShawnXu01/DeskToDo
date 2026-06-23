"""任务数据模型：日历任务（dated）与无日期任务（floating）。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class Priority(Enum):
    """优先级，数值越小越重要，用于排序。"""

    RED = 1
    GREEN = 2
    ORANGE = 3
    WHITE = 4


class RecurrenceType(Enum):
    ONCE = "once"
    DAILY_RANGE = "daily_range"
    WEEKLY = "weekly"
    SPECIFIC_DATES = "specific_dates"


def _date_to_str(d: date) -> str:
    return d.isoformat()


def _str_to_date(s: str) -> date:
    return date.fromisoformat(s)


@dataclass
class RecurrenceRule:
    """周期规则，4 种类型互斥，构造时按类型校验必填字段。"""

    type: RecurrenceType
    date: Optional[date] = None
    start: Optional[date] = None
    end: Optional[date] = None
    weekdays: Optional[list[int]] = None
    dates: Optional[list[date]] = None

    def __post_init__(self) -> None:
        if self.type is RecurrenceType.ONCE and self.date is None:
            raise ValueError("ONCE 类型必须提供 date")
        if self.type is RecurrenceType.DAILY_RANGE and (self.start is None or self.end is None):
            raise ValueError("DAILY_RANGE 类型必须提供 start 和 end")
        if self.type is RecurrenceType.DAILY_RANGE and self.start is not None and self.end is not None:
            if self.start > self.end:
                raise ValueError("DAILY_RANGE 的 start 不能晚于 end")
        if self.type is RecurrenceType.WEEKLY and not self.weekdays:
            raise ValueError("WEEKLY 类型必须提供 weekdays")
        if self.type is RecurrenceType.WEEKLY and self.weekdays is not None:
            if any(w < 1 or w > 7 for w in self.weekdays):
                raise ValueError("weekdays 取值必须是 1(周一)~7(周日)")
        if self.type is RecurrenceType.WEEKLY and self.start is not None and self.end is not None:
            if self.start > self.end:
                raise ValueError("WEEKLY 的 start 不能晚于 end")
        if self.type is RecurrenceType.SPECIFIC_DATES and not self.dates:
            raise ValueError("SPECIFIC_DATES 类型必须提供 dates")

    def occurs_on(self, day: date) -> bool:
        if self.type is RecurrenceType.ONCE:
            return day == self.date
        if self.type is RecurrenceType.DAILY_RANGE:
            return self.start <= day <= self.end
        if self.type is RecurrenceType.WEEKLY:
            if self.start is not None and day < self.start:
                return False
            if self.end is not None and day > self.end:
                return False
            return day.isoweekday() in self.weekdays
        if self.type is RecurrenceType.SPECIFIC_DATES:
            return day in self.dates
        raise AssertionError(f"未知的周期类型: {self.type}")

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "date": _date_to_str(self.date) if self.date else None,
            "start": _date_to_str(self.start) if self.start else None,
            "end": _date_to_str(self.end) if self.end else None,
            "weekdays": self.weekdays,
            "dates": [_date_to_str(d) for d in self.dates] if self.dates else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecurrenceRule":
        return cls(
            type=RecurrenceType(data["type"]),
            date=_str_to_date(data["date"]) if data.get("date") else None,
            start=_str_to_date(data["start"]) if data.get("start") else None,
            end=_str_to_date(data["end"]) if data.get("end") else None,
            weekdays=data.get("weekdays"),
            dates=[_str_to_date(d) for d in data["dates"]] if data.get("dates") else None,
        )


@dataclass
class DatedTask:
    """挂在日历某天/某些天上的任务，支持周期规则与按次完成。"""

    id: str
    name: str
    priority: Priority
    recurrence: RecurrenceRule
    created_at: datetime
    updated_at: datetime
    completed_dates: set[date] = field(default_factory=set)
    deleted_at: Optional[datetime] = None
    source: str = "local"

    @classmethod
    def create(cls, name: str, priority: Priority, recurrence: RecurrenceRule) -> "DatedTask":
        now = datetime.now()
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            priority=priority,
            recurrence=recurrence,
            created_at=now,
            updated_at=now,
        )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def is_completed_on(self, day: date) -> bool:
        return day in self.completed_dates

    def set_completed(self, day: date, completed: bool) -> None:
        if completed:
            self.completed_dates.add(day)
        else:
            self.completed_dates.discard(day)
        self.updated_at = datetime.now()

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now()
        self.updated_at = self.deleted_at

    def sort_key(self, day: date) -> tuple[bool, int]:
        """未完成靠前、按优先级升序；已完成沉底（组内仍按优先级排）。"""
        return (self.is_completed_on(day), self.priority.value)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority.value,
            "recurrence": self.recurrence.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_dates": [_date_to_str(d) for d in sorted(self.completed_dates)],
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DatedTask":
        return cls(
            id=data["id"],
            name=data["name"],
            priority=Priority(data["priority"]),
            recurrence=RecurrenceRule.from_dict(data["recurrence"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            completed_dates={_str_to_date(d) for d in data.get("completed_dates", [])},
            deleted_at=datetime.fromisoformat(data["deleted_at"]) if data.get("deleted_at") else None,
            source=data.get("source", "local"),
        )


@dataclass
class FloatingTask:
    """无具体日期的单次待办，独立于日历，不会出现在日历格子里。"""

    id: str
    name: str
    priority: Priority
    created_at: datetime
    updated_at: datetime
    completed: bool = False
    completed_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    source: str = "local"

    @classmethod
    def create(cls, name: str, priority: Priority) -> "FloatingTask":
        now = datetime.now()
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            priority=priority,
            created_at=now,
            updated_at=now,
        )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def set_completed(self, completed: bool) -> None:
        self.completed = completed
        self.completed_at = datetime.now() if completed else None
        self.updated_at = datetime.now()

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now()
        self.updated_at = self.deleted_at

    def sort_key(self) -> tuple[bool, int]:
        return (self.completed, self.priority.value)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed": self.completed,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FloatingTask":
        return cls(
            id=data["id"],
            name=data["name"],
            priority=Priority(data["priority"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            completed=data.get("completed", False),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            deleted_at=datetime.fromisoformat(data["deleted_at"]) if data.get("deleted_at") else None,
            source=data.get("source", "local"),
        )
