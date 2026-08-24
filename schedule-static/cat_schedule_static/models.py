from __future__ import annotations

from dataclasses import dataclass, field


class ScheduleParseError(ValueError):
    """Raised when an input file is not a supported schedule page."""


class ScheduleBuildError(ValueError):
    """Raised when parsed data is not safe or complete enough to publish."""


@dataclass(frozen=True)
class CourseTimeSegment:
    weekday: int
    weekday_label: str
    start_section: int | None
    end_section: int | None
    time_text: str
    location: str | None = None


@dataclass(frozen=True)
class CourseDetailRow:
    course_code: str | None
    class_no: str | None
    course_name: str
    teacher: str | None
    segments: list[CourseTimeSegment]
    credit: str | None
    course_attribute: str | None
    selection_stage: str | None


@dataclass(frozen=True)
class ScheduleOccurrence:
    course_code: str | None
    class_no: str | None
    course_name: str
    teacher: str | None
    weekday: int
    weekday_label: str
    block_start: int
    block_end: int
    block_label_start: str
    block_label_end: str
    time_text: str
    week_text: str
    week_numbers: list[int]
    location: str | None
    credit: str | None
    course_attribute: str | None
    selection_stage: str | None


@dataclass
class ScheduleParseResult:
    term: str | None
    available_terms: list[str]
    entries: list[ScheduleOccurrence]
    source_encoding: str | None
    warnings: list[str] = field(default_factory=list)
