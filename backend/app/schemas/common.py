from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class UserBrief(BaseModel):
    id: str
    display_name: str
    email: str


class EnqueueResult(BaseModel):
    task_id: str
    queue_job_id: str | None = None


class Timestamped(BaseModel):
    created_at: datetime


class ApiEnvelope(BaseModel):
    ok: bool
    code: str
    message: str
    data: Any = None

