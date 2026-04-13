from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import api_success
from app.db.session import get_db
from app.models import User
from app.services.grade_service import get_grades_payload
from app.services.task_service import enqueue_grade_check


router = APIRouter(prefix="/grades", tags=["grades"])


@router.get("")
def get_grades(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    return api_success(get_grades_payload(db, user=current_user))


@router.post("/check-now")
def check_grades_now(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    task_log = enqueue_grade_check(db, user=current_user)
    return api_success(
        {"task_id": str(task_log.id), "queue_job_id": task_log.queue_job_id},
        message="成绩检查任务已入队",
    )

