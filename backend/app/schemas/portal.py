from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PortalAccountUpsertRequest(BaseModel):
    portal_username: str = Field(min_length=1, max_length=100)
    portal_password: str = Field(min_length=1, max_length=128)


class PortalAccountResponse(BaseModel):
    is_bound: bool
    portal_username: str | None = None
    last_successful_login_at: datetime | None = None
    last_schedule_refresh_at: datetime | None = None
    last_grade_check_at: datetime | None = None
    last_failure_message: str | None = None
    has_reusable_cookie: bool = False

