from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import utcnow
from app.models import GradeNotification, GradeRecord, GradeSnapshot, User
from app.portal.parsers import GradeItemParsed, GradesParseResult
from app.services.notification_service import send_grade_notification_email


def _score_completeness(item: GradeItemParsed) -> tuple[int, int, int]:
    """
    同一 record_key 如果在一次解析中出现多次，保留信息更完整的一条。
    """

    return (
        1 if item.score not in (None, "") else 0,
        1 if item.score_numeric is not None else 0,
        len(item.raw_payload.get("raw_columns", [])) if isinstance(item.raw_payload, dict) else 0,
    )


def _dedupe_grade_items(items: list[GradeItemParsed]) -> list[GradeItemParsed]:
    deduped: dict[str, GradeItemParsed] = {}
    order: list[str] = []
    for item in items:
        if item.record_key not in deduped:
            deduped[item.record_key] = item
            order.append(item.record_key)
            continue
        existing = deduped[item.record_key]
        if _score_completeness(item) >= _score_completeness(existing):
            deduped[item.record_key] = item
    return [deduped[record_key] for record_key in order]


def _should_notify_score_change(*, initial_sync: bool, previous_score: str | None, current_score: str | None) -> bool:
    if initial_sync:
        return False
    return bool(current_score) and (previous_score is None or previous_score == "")


def sync_grades(db: Session, *, user: User, html: str, parsed: GradesParseResult) -> list[GradeRecord]:
    unique_items = _dedupe_grade_items(parsed.items)
    initial_sync = (
        db.scalar(select(GradeRecord.id).where(GradeRecord.user_id == user.id).limit(1)) is None
    )
    snapshot = GradeSnapshot(
        user_id=user.id,
        source_mode=settings.portal_mode,
        raw_html=html,
        record_count=len(unique_items),
    )
    db.add(snapshot)
    db.flush()

    changed_records: list[GradeRecord] = []
    now = utcnow()
    existing_records = {
        record.record_key: record
        for record in db.scalars(
            select(GradeRecord).where(
                GradeRecord.user_id == user.id,
                GradeRecord.record_key.in_([item.record_key for item in unique_items]),
            )
        )
    }

    for item in unique_items:
        record = existing_records.get(item.record_key)
        previous_score = record.score if record else None
        if not record:
            record = GradeRecord(
                user_id=user.id,
                term=item.term,
                record_key=item.record_key,
                course_code=item.course_code,
                course_name=item.course_name,
                first_seen_at=now,
            )
            db.add(record)
            existing_records[item.record_key] = record
        record.term = item.term
        record.course_code = item.course_code
        record.course_name = item.course_name
        record.score = item.score
        record.score_numeric = item.score_numeric
        record.score_flag = item.score_flag
        record.grade_point_text = item.grade_point_text
        record.credit = item.credit
        record.total_hours = item.total_hours
        record.assessment_method = item.assessment_method
        record.course_attribute = item.course_attribute
        record.course_nature = item.course_nature
        record.raw_payload = item.raw_payload
        record.last_seen_at = now
        record.last_checked_at = now
        if _should_notify_score_change(
            initial_sync=initial_sync,
            previous_score=previous_score,
            current_score=item.score,
        ):
            changed_records.append(record)

    db.commit()
    return changed_records


def notify_new_grades(db: Session, *, user: User, changed_records: list[GradeRecord]) -> int:
    if not changed_records or not user.email_notifications_enabled:
        return 0
    target_email = user.notification_email or user.email
    sent_count = 0
    for record in changed_records:
        notification_key = f"{record.record_key}:{record.score or 'EMPTY'}"
        exists = db.scalar(select(GradeNotification).where(GradeNotification.notification_key == notification_key))
        if exists:
            continue
        subject = f"新成绩通知: {record.course_name}"
        html_body = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.6;">
          <h2>有一门课程出了新成绩</h2>
          <p><strong>课程：</strong>{record.course_name}</p>
          <p><strong>学期：</strong>{record.term}</p>
          <p><strong>成绩：</strong>{record.score}</p>
          <p><strong>学分：</strong>{record.credit or '-'}</p>
          <p>打开C.A.T.课表即可查看缓存详情。</p>
        </div>
        """
        send_grade_notification_email(to_email=target_email, subject=subject, html_body=html_body)
        db.add(
            GradeNotification(
                user_id=user.id,
                grade_record_id=record.id,
                notification_key=notification_key,
                event_type="score_available",
                sent_to_email=target_email,
                payload={"course_name": record.course_name, "score": record.score},
            )
        )
        sent_count += 1
    db.commit()
    return sent_count


def get_grades_payload(db: Session, *, user: User) -> dict:
    records = list(
        db.scalars(
            select(GradeRecord).where(GradeRecord.user_id == user.id).order_by(GradeRecord.term.desc(), GradeRecord.course_name)
        )
    )
    grouped: dict[str, list[dict]] = defaultdict(list)
    last_checked_at = None
    for record in records:
        grouped[record.term].append(
            {
                "id": str(record.id),
                "term": record.term,
                "course_code": record.course_code,
                "course_name": record.course_name,
                "score": record.score,
                "score_numeric": float(record.score_numeric) if record.score_numeric is not None else None,
                "score_flag": record.score_flag,
                "grade_point_text": record.grade_point_text,
                "credit": record.credit,
                "total_hours": record.total_hours,
                "assessment_method": record.assessment_method,
                "course_attribute": record.course_attribute,
                "course_nature": record.course_nature,
                "last_checked_at": record.last_checked_at,
            }
        )
        if last_checked_at is None or record.last_checked_at > last_checked_at:
            last_checked_at = record.last_checked_at
    return {
        "last_checked_at": last_checked_at,
        "notification_email": user.notification_email or user.email,
        "email_notifications_enabled": user.email_notifications_enabled,
        "terms": [{"term": term, "items": items} for term, items in grouped.items()],
    }
