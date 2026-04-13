from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class GradeItem(BaseModel):
    id: str
    term: str
    course_code: str | None = None
    course_name: str
    score: str | None = None
    score_numeric: float | None = None
    score_flag: str | None = None
    grade_point_text: str | None = None
    credit: str | None = None
    total_hours: str | None = None
    assessment_method: str | None = None
    course_attribute: str | None = None
    course_nature: str | None = None
    last_checked_at: datetime


class GradeTermGroup(BaseModel):
    term: str
    items: list[GradeItem]


class GradesPayload(BaseModel):
    last_checked_at: datetime | None = None
    notification_email: str | None = None
    email_notifications_enabled: bool
    terms: list[GradeTermGroup]

