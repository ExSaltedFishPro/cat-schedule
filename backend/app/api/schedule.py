from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import api_success
from app.db.session import get_db
from app.models import User
from app.services.schedule_service import get_schedule_payload
from app.services.task_service import enqueue_schedule_refresh


router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("")
def get_schedule(
    term: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return api_success(get_schedule_payload(db, user=current_user, term=term))


@router.post("/refresh")
def refresh_schedule(
    term: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    task_log = enqueue_schedule_refresh(db, user=current_user, term=term)
    return api_success(
        {"task_id": str(task_log.id), "queue_job_id": task_log.queue_job_id},
        message="课表刷新任务已入队",
    )

