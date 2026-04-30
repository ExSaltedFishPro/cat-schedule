from __future__ import annotations

import logging
from contextlib import contextmanager

from redis import Redis

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import PortalAccount, User
from app.services.grade_service import notify_new_exams, notify_new_grades, sync_exams, sync_grades
from app.services.portal_service import fetch_and_parse_exams, fetch_and_parse_grades, fetch_and_parse_schedule
from app.services.schedule_service import replace_schedule_snapshot
from app.services.task_service import mark_task_finished, mark_task_started


logger = logging.getLogger(__name__)


@contextmanager
def redis_lock(name: str, timeout_seconds: int = 120):
    redis = Redis.from_url(settings.redis_url)
    lock = redis.lock(name, timeout=timeout_seconds, blocking_timeout=1)
    acquired = lock.acquire(blocking=False)
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()


def refresh_schedule_job(user_id: str, term: str | None = None, task_log_id: str | None = None) -> None:
    with SessionLocal() as db:
        if task_log_id:
            mark_task_started(db, task_log_id)
        with redis_lock(f"lock:schedule:{user_id}:{term or 'current'}") as acquired:
            if not acquired:
                if task_log_id:
                    mark_task_finished(db, task_log_id, status="skipped", message="已有相同课表刷新任务在执行")
                return
            try:
                user = db.get(User, user_id)
                if not user or not user.portal_account:
                    raise ValueError("user portal account not found")
                html, parsed = fetch_and_parse_schedule(db, user.portal_account, term=term)
                snapshot = replace_schedule_snapshot(db, user=user, html=html, parsed=parsed, requested_term=term)
                if task_log_id:
                    mark_task_finished(
                        db,
                        task_log_id,
                        status="succeeded",
                        message=f"课表刷新完成，共 {snapshot.entry_count} 条课表记录",
                    )
            except Exception as exc:
                logger.exception("refresh_schedule_job failed: %s", exc)
                db.rollback()
                if task_log_id:
                    mark_task_finished(db, task_log_id, status="failed", error_text=str(exc))
                raise


def check_grades_job(user_id: str, task_log_id: str | None = None) -> None:
    with SessionLocal() as db:
        if task_log_id:
            mark_task_started(db, task_log_id)
        with redis_lock(f"lock:grades:{user_id}") as acquired:
            if not acquired:
                if task_log_id:
                    mark_task_finished(db, task_log_id, status="skipped", message="已有成绩检查任务在执行")
                return
            try:
                user = db.get(User, user_id)
                if not user or not user.portal_account:
                    raise ValueError("user portal account not found")
                html, parsed = fetch_and_parse_grades(db, user.portal_account)
                changed_records = sync_grades(db, user=user, html=html, parsed=parsed)
                sent_count = notify_new_grades(db, user=user, changed_records=changed_records)
                if task_log_id:
                    mark_task_finished(
                        db,
                        task_log_id,
                        status="succeeded",
                        message=f"成绩检查完成，本次发送 {sent_count} 封邮件",
                    )
            except Exception as exc:
                logger.exception("check_grades_job failed: %s", exc)
                db.rollback()
                if task_log_id:
                    mark_task_finished(db, task_log_id, status="failed", error_text=str(exc))
                raise


def check_exams_job(user_id: str) -> None:
    with SessionLocal() as db:
        with redis_lock(f"lock:exams:{user_id}") as acquired:
            if not acquired:
                return
            try:
                user = db.get(User, user_id)
                if not user or not user.portal_account:
                    raise ValueError("user portal account not found")
                html, parsed = fetch_and_parse_exams(db, user.portal_account)
                changed_records = sync_exams(db, user=user, html=html, parsed=parsed)
                sent_count = notify_new_exams(db, user=user, changed_records=changed_records)
                logger.info("exam check finished for user=%s, sent=%s", user_id, sent_count)
            except Exception as exc:
                logger.exception("check_exams_job failed: %s", exc)
                db.rollback()
                raise


def scheduled_grade_check_job() -> None:
    with SessionLocal() as db:
        users = db.query(User).join(PortalAccount).filter(User.email_notifications_enabled.is_(True)).all()
        for user in users:
            check_grades_job(str(user.id))
        exam_users = db.query(User).join(PortalAccount).all()
        for user in exam_users:
            check_exams_job(str(user.id))
