from __future__ import annotations

import uuid

from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import utcnow
from app.models import TaskLog, User


def get_queue() -> Queue:
    connection = Redis.from_url(settings.redis_url)
    return Queue(settings.queue_name, connection=connection)


def create_task_log(
    db: Session,
    *,
    job_name: str,
    user_id: uuid.UUID | None,
    payload: dict,
) -> TaskLog:
    task_log = TaskLog(job_name=job_name, user_id=user_id, payload=payload, status="queued")
    db.add(task_log)
    db.commit()
    db.refresh(task_log)
    return task_log


def enqueue_schedule_refresh(db: Session, *, user: User, term: str | None = None) -> TaskLog:
    task_log = create_task_log(db, job_name="refresh_schedule", user_id=user.id, payload={"term": term})
    job = get_queue().enqueue("app.tasks.jobs.refresh_schedule_job", str(user.id), term, str(task_log.id))
    task_log.queue_job_id = job.id
    db.commit()
    return task_log


def enqueue_grade_check(db: Session, *, user: User) -> TaskLog:
    task_log = create_task_log(db, job_name="check_grades", user_id=user.id, payload={})
    job = get_queue().enqueue("app.tasks.jobs.check_grades_job", str(user.id), str(task_log.id))
    task_log.queue_job_id = job.id
    db.commit()
    return task_log


def enqueue_scheduled_grade_check() -> str:
    job = get_queue().enqueue("app.tasks.jobs.scheduled_grade_check_job")
    return job.id


def mark_task_started(db: Session, task_log_id: str) -> TaskLog:
    task_log = db.get(TaskLog, task_log_id)
    if not task_log:
        raise AppError(404, "TASK_LOG_NOT_FOUND", "任务记录不存在")
    task_log.status = "running"
    task_log.started_at = utcnow()
    db.commit()
    return task_log


def mark_task_finished(
    db: Session,
    task_log_id: str,
    *,
    status: str,
    message: str | None = None,
    error_text: str | None = None,
) -> None:
    task_log = db.get(TaskLog, task_log_id)
    if not task_log:
        return
    task_log.status = status
    task_log.message = message
    task_log.error_text = error_text
    task_log.finished_at = utcnow()
    db.commit()
