from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import ScheduleEntry, ScheduleSnapshot, User
from app.portal.parsers import LessonsParseResult


UNKNOWN_TERM = "unknown"


def _normalize_term(term: str | None) -> str | None:
    value = (term or "").strip()
    if not value or value.lower() == UNKNOWN_TERM:
        return None
    return value


def _payload_term(term: str | None) -> str | None:
    return _normalize_term(term)


def _entry_dedupe_key(entry: ScheduleEntry) -> tuple:
    return (
        entry.course_code,
        entry.class_no,
        entry.course_name,
        entry.teacher,
        entry.weekday,
        entry.block_start,
        entry.block_end,
        tuple(entry.week_numbers or []),
        entry.location,
        entry.time_text,
    )


def replace_schedule_snapshot(
    db: Session,
    *,
    user: User,
    html: str,
    parsed: LessonsParseResult,
    requested_term: str | None = None,
) -> ScheduleSnapshot:
    term = _normalize_term(parsed.term) or _normalize_term(requested_term) or UNKNOWN_TERM
    for snapshot in db.scalars(
        select(ScheduleSnapshot).where(ScheduleSnapshot.user_id == user.id, ScheduleSnapshot.term == term)
    ):
        snapshot.is_current = False

    snapshot = ScheduleSnapshot(
        user_id=user.id,
        term=term,
        source_mode=settings.portal_mode,
        raw_html=html,
        raw_summary=parsed.raw_summary,
        entry_count=len(parsed.entries),
        is_current=True,
    )
    db.add(snapshot)
    db.flush()

    for item in parsed.entries:
        db.add(
            ScheduleEntry(
                snapshot_id=snapshot.id,
                user_id=user.id,
                term=term,
                course_code=item.course_code,
                class_no=item.class_no,
                course_name=item.course_name,
                teacher=item.teacher,
                weekday=item.weekday,
                weekday_label=item.weekday_label,
                block_start=item.block_start,
                block_end=item.block_end,
                block_label_start=item.block_label_start,
                block_label_end=item.block_label_end,
                time_text=item.time_text,
                week_text=item.week_text,
                week_numbers=item.week_numbers,
                location=item.location,
                credit=item.credit,
                course_attribute=item.course_attribute,
                selection_stage=item.selection_stage,
                raw_payload=item.raw_payload,
            )
        )

    db.commit()
    db.refresh(snapshot)
    return snapshot


def _entry_to_payload(entry: ScheduleEntry) -> dict:
    return {
        "id": str(entry.id),
        "course_code": entry.course_code,
        "class_no": entry.class_no,
        "course_name": entry.course_name,
        "teacher": entry.teacher,
        "weekday": entry.weekday,
        "weekday_label": entry.weekday_label,
        "block_start": entry.block_start,
        "block_end": entry.block_end,
        "block_label_start": entry.block_label_start,
        "block_label_end": entry.block_label_end,
        "time_text": entry.time_text,
        "week_text": entry.week_text,
        "week_numbers": entry.week_numbers,
        "location": entry.location,
        "credit": entry.credit,
        "course_attribute": entry.course_attribute,
        "selection_stage": entry.selection_stage,
    }


def get_schedule_payload(db: Session, *, user: User, term: str | None = None) -> dict:
    raw_terms = list(
        db.scalars(
            select(ScheduleSnapshot.term)
            .where(ScheduleSnapshot.user_id == user.id)
            .distinct()
            .order_by(ScheduleSnapshot.term.desc())
        )
    )
    available_terms: list[str] = []
    for item in raw_terms:
        normalized = _normalize_term(item)
        if normalized and normalized not in available_terms:
            available_terms.append(normalized)

    query = select(ScheduleSnapshot).options(selectinload(ScheduleSnapshot.entries)).where(
        ScheduleSnapshot.user_id == user.id,
        ScheduleSnapshot.is_current.is_(True),
    )
    normalized_term = _normalize_term(term)
    if normalized_term:
        query = query.where(ScheduleSnapshot.term == normalized_term)
        snapshot = db.scalars(query).first()
    else:
        snapshots = list(db.scalars(query.order_by(ScheduleSnapshot.refreshed_at.desc())))
        snapshot = next((item for item in snapshots if _normalize_term(item.term)), snapshots[0] if snapshots else None)
    if not snapshot:
        return {
            "term": normalized_term,
            "available_terms": available_terms,
            "last_refreshed_at": None,
            "total_entries": 0,
            "entries": [],
            "weeks": [],
        }

    deduped_entries: list[ScheduleEntry] = []
    seen_entry_keys: set[tuple] = set()
    for entry in sorted(snapshot.entries, key=lambda item: (item.weekday, item.block_start, item.course_name)):
        dedupe_key = _entry_dedupe_key(entry)
        if dedupe_key in seen_entry_keys:
            continue
        seen_entry_keys.add(dedupe_key)
        deduped_entries.append(entry)

    entries = deduped_entries
    week_numbers = sorted({week for entry in entries for week in entry.week_numbers})
    weeks_payload = []
    for week_number in week_numbers:
        by_day: dict[int, list[dict]] = defaultdict(list)
        for entry in entries:
            if week_number in entry.week_numbers:
                by_day[entry.weekday].append(_entry_to_payload(entry))
        weeks_payload.append(
            {
                "week_number": week_number,
                "days": [
                    {
                        "weekday": weekday,
                        "weekday_label": f"星期{'一二三四五六日'[weekday - 1]}",
                        "items": sorted(by_day.get(weekday, []), key=lambda item: (item["block_start"], item["course_name"])),
                    }
                    for weekday in range(1, 8)
                ],
            }
        )
    return {
        "term": _payload_term(snapshot.term),
        "available_terms": available_terms,
        "last_refreshed_at": snapshot.refreshed_at,
        "total_entries": len(entries),
        "entries": [_entry_to_payload(entry) for entry in entries],
        "weeks": weeks_payload,
    }
