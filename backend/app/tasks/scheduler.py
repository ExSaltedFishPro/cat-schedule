from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from app.core.config import settings
from app.core.logging import configure_logging
from app.services.task_service import enqueue_scheduled_grade_check


logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    scheduler = BlockingScheduler(timezone=settings.scheduler_timezone)
    scheduler.add_job(
        enqueue_scheduled_grade_check,
        "interval",
        minutes=settings.grade_check_interval_minutes,
        id="scheduled-grade-check",
        replace_existing=True,
    )
    startup_job_id = enqueue_scheduled_grade_check()
    logger.info("Initial grade/exam check enqueued on scheduler startup, job_id=%s", startup_job_id)
    logger.info("Grade check scheduler started, interval=%s minutes", settings.grade_check_interval_minutes)
    scheduler.start()


if __name__ == "__main__":
    main()
