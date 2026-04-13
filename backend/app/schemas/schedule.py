from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ScheduleEntryItem(BaseModel):
    id: str
    course_code: str | None = None
    class_no: str | None = None
    course_name: str
    teacher: str | None = None
    weekday: int
    weekday_label: str
    block_start: int
    block_end: int
    block_label_start: str
    block_label_end: str
    time_text: str
    week_text: str
    week_numbers: list[int]
    location: str | None = None
    credit: str | None = None
    course_attribute: str | None = None
    selection_stage: str | None = None


class ScheduleDayView(BaseModel):
    weekday: int
    weekday_label: str
    items: list[ScheduleEntryItem]


class ScheduleWeekView(BaseModel):
    week_number: int
    days: list[ScheduleDayView]


class SchedulePayload(BaseModel):
    term: str | None = None
    available_terms: list[str]
    last_refreshed_at: datetime | None = None
    total_entries: int
    entries: list[ScheduleEntryItem]
    weeks: list[ScheduleWeekView]

