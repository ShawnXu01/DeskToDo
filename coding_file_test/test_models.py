"""Phase 1 自检：验证 deskcal.core.models 的核心逻辑。"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from deskcal.core.models import (
    DatedTask,
    FloatingTask,
    Priority,
    RecurrenceRule,
    RecurrenceType,
)


def test_recurrence_once_occurs_on():
    rule = RecurrenceRule(type=RecurrenceType.ONCE, date=date(2026, 6, 20))
    assert rule.occurs_on(date(2026, 6, 20))
    assert not rule.occurs_on(date(2026, 6, 21))


def test_recurrence_daily_range_occurs_on():
    rule = RecurrenceRule(type=RecurrenceType.DAILY_RANGE, start=date(2026, 6, 1), end=date(2026, 6, 10))
    assert rule.occurs_on(date(2026, 6, 1))
    assert rule.occurs_on(date(2026, 6, 10))
    assert rule.occurs_on(date(2026, 6, 5))
    assert not rule.occurs_on(date(2026, 6, 11))


def test_recurrence_weekly_occurs_on():
    rule = RecurrenceRule(type=RecurrenceType.WEEKLY, weekdays=[3, 5])  # 周三、周五
    assert rule.occurs_on(date(2026, 6, 17))  # 2026-06-17 是周三
    assert rule.occurs_on(date(2026, 6, 19))  # 周五
    assert not rule.occurs_on(date(2026, 6, 18))  # 周四


def test_recurrence_specific_dates_occurs_on():
    rule = RecurrenceRule(
        type=RecurrenceType.SPECIFIC_DATES,
        dates=[date(2026, 6, 3), date(2026, 6, 5), date(2026, 6, 9)],
    )
    assert rule.occurs_on(date(2026, 6, 3))
    assert not rule.occurs_on(date(2026, 6, 4))


def test_recurrence_validation_rejects_missing_fields():
    with pytest.raises(ValueError):
        RecurrenceRule(type=RecurrenceType.ONCE)
    with pytest.raises(ValueError):
        RecurrenceRule(type=RecurrenceType.DAILY_RANGE, start=date(2026, 6, 5), end=date(2026, 6, 1))
    with pytest.raises(ValueError):
        RecurrenceRule(type=RecurrenceType.WEEKLY, weekdays=[8])
    with pytest.raises(ValueError):
        RecurrenceRule(type=RecurrenceType.SPECIFIC_DATES)


def test_recurrence_round_trip_dict():
    rule = RecurrenceRule(type=RecurrenceType.WEEKLY, weekdays=[1, 3, 5])
    restored = RecurrenceRule.from_dict(rule.to_dict())
    assert restored.type is RecurrenceType.WEEKLY
    assert restored.weekdays == [1, 3, 5]


def test_dated_task_per_occurrence_completion():
    rule = RecurrenceRule(type=RecurrenceType.WEEKLY, weekdays=[3])
    task = DatedTask.create("每周三开会", Priority.RED, rule)
    wed1, wed2 = date(2026, 6, 17), date(2026, 6, 24)

    task.set_completed(wed1, True)
    assert task.is_completed_on(wed1)
    assert not task.is_completed_on(wed2)  # 只完成了这一次，不影响未来的实例


def test_dated_task_sort_key_priority_and_completion():
    rule_once = RecurrenceRule(type=RecurrenceType.ONCE, date=date(2026, 6, 20))
    high = DatedTask.create("高优先级未完成", Priority.RED, rule_once)
    low_done = DatedTask.create("低优先级已完成", Priority.WHITE, rule_once)
    high_done = DatedTask.create("高优先级已完成", Priority.RED, rule_once)
    low_done.set_completed(date(2026, 6, 20), True)
    high_done.set_completed(date(2026, 6, 20), True)

    day = date(2026, 6, 20)
    tasks = [low_done, high, high_done]
    tasks.sort(key=lambda t: t.sort_key(day))

    # 未完成的排最前；已完成的沉底，但已完成组内仍按优先级排序
    assert tasks[0] is high
    assert tasks[1] is high_done
    assert tasks[2] is low_done


def test_dated_task_soft_delete_and_round_trip():
    rule = RecurrenceRule(type=RecurrenceType.ONCE, date=date(2026, 6, 20))
    task = DatedTask.create("任务", Priority.GREEN, rule)
    task.soft_delete()
    assert task.is_deleted

    restored = DatedTask.from_dict(task.to_dict())
    assert restored.is_deleted
    assert restored.priority is Priority.GREEN
    assert restored.recurrence.type is RecurrenceType.ONCE


def test_floating_task_completion_and_round_trip():
    task = FloatingTask.create("论文推进计划", Priority.ORANGE)
    assert not task.completed

    task.set_completed(True)
    assert task.completed
    assert task.completed_at is not None

    restored = FloatingTask.from_dict(task.to_dict())
    assert restored.completed
    assert restored.priority is Priority.ORANGE


def test_floating_task_sort_key():
    done = FloatingTask.create("已完成", Priority.RED)
    done.set_completed(True)
    todo = FloatingTask.create("待办", Priority.WHITE)

    tasks = [done, todo]
    tasks.sort(key=lambda t: t.sort_key())
    assert tasks[0] is todo
    assert tasks[1] is done
