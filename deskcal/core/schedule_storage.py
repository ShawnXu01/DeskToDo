"""版本化课表 JSON 存储。"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from deskcal.core.schedule_models import CourseEntry, Term
from deskcal.core.storage import atomic_write_json, get_data_dir

SCHEDULE_FILE_NAME = "schedule.json"
SCHEDULE_SCHEMA_VERSION = 1


def get_schedule_file() -> Path:
    return get_data_dir() / SCHEDULE_FILE_NAME


class ScheduleStore:
    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or get_schedule_file()
        self.terms: dict[str, Term] = {}
        self.active_term_id: Optional[str] = None

    def load(self) -> None:
        self.terms = {}
        self.active_term_id = None
        if not self.file_path.exists():
            return
        with open(self.file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        version = raw.get("version")
        if version != SCHEDULE_SCHEMA_VERSION:
            raise ValueError(f"不支持的课表数据版本: {version}")
        for item in raw.get("terms", []):
            term = Term.from_dict(item)
            self.terms[term.id] = term
        candidate = raw.get("active_term_id")
        self.active_term_id = candidate if candidate in self.terms else None

    def save(self) -> None:
        atomic_write_json(
            self.file_path,
            {
                "version": SCHEDULE_SCHEMA_VERSION,
                "active_term_id": self.active_term_id,
                "terms": [term.to_dict() for term in self.terms.values()],
            },
        )

    def add_term(self, term: Term) -> None:
        self.terms[term.id] = term
        if self.active_term_id is None:
            self.active_term_id = term.id

    def get_active_term(self, today: Optional[date] = None) -> Optional[Term]:
        if self.active_term_id in self.terms:
            return self.terms[self.active_term_id]
        return self.choose_default_term(today or date.today())

    def choose_default_term(self, today: date) -> Optional[Term]:
        current = [
            term
            for term in self.terms.values()
            if not term.archived and term.start_date <= today <= term.end_date
        ]
        if current:
            chosen = min(current, key=lambda term: term.start_date)
        else:
            available = [term for term in self.terms.values() if not term.archived]
            if not available:
                return None
            chosen = min(available, key=lambda term: abs((term.end_date - today).days))
        self.active_term_id = chosen.id
        return chosen

    def set_active_term(self, term_id: str) -> None:
        if term_id not in self.terms:
            raise KeyError(f"学期不存在: {term_id}")
        self.active_term_id = term_id

    def remove_term(self, term_id: str) -> None:
        if term_id not in self.terms:
            raise KeyError(f"学期不存在: {term_id}")
        del self.terms[term_id]
        if self.active_term_id == term_id:
            self.active_term_id = None
            self.choose_default_term(date.today())

    def duplicate_term(self, term_id: str, new_name: str) -> Term:
        source = self.terms[term_id]
        duplicate = Term.create(new_name, source.start_date, source.end_date)
        for course in source.courses:
            duplicate.add_course(
                CourseEntry.create(
                    code=course.code,
                    title=course.title,
                    instructor=course.instructor,
                    location=course.location,
                    weekdays=list(course.weekdays),
                    start_time=course.start_time,
                    end_time=course.end_time,
                    color=course.color,
                    notes=course.notes,
                )
            )
        self.add_term(duplicate)
        return duplicate
