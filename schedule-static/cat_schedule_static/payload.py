from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone

from cat_schedule_static import __version__
from cat_schedule_static.models import ScheduleBuildError, ScheduleOccurrence, ScheduleParseResult


WEEKDAY_LABELS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def _stable_entry_id(entry: ScheduleOccurrence) -> str:
    canonical = json.dumps(
        [
            entry.course_code,
            entry.class_no,
            entry.course_name,
            entry.teacher,
            entry.weekday,
            entry.block_start,
            entry.block_end,
            entry.week_numbers,
            entry.location,
            entry.time_text,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def _entry_payload(entry: ScheduleOccurrence) -> dict:
    payload = asdict(entry)
    payload["id"] = _stable_entry_id(entry)
    return {"id": payload.pop("id"), **payload}


def _build_weeks(entries: list[dict], *, include_incomplete: bool) -> list[dict]:
    week_numbers = sorted({week for entry in entries for week in entry["week_numbers"]})
    if include_incomplete and any(not entry["week_numbers"] for entry in entries):
        week_numbers = [0, *week_numbers]

    weeks: list[dict] = []
    for week_number in week_numbers:
        days: list[dict] = []
        for weekday, weekday_label in enumerate(WEEKDAY_LABELS, start=1):
            day_entries = [
                entry
                for entry in entries
                if entry["weekday"] == weekday
                and (
                    (week_number == 0 and not entry["week_numbers"])
                    or week_number in entry["week_numbers"]
                )
            ]
            day_entries.sort(key=lambda item: (item["block_start"], item["block_end"], item["course_name"]))
            days.append(
                {
                    "weekday": weekday,
                    "weekday_label": weekday_label,
                    "items": day_entries,
                }
            )
        weeks.append({"week_number": week_number, "days": days})
    return weeks


def build_schedule_document(
    parsed: ScheduleParseResult,
    *,
    source_sha256: str,
    term: str | None = None,
    term_start_date: str | None = None,
    title: str = "C.A.T. Schedule",
    allow_empty: bool = False,
    allow_incomplete: bool = False,
    generated_at: str | None = None,
) -> dict:
    resolved_term = (term or parsed.term or "").strip()
    if not resolved_term:
        raise ScheduleBuildError("无法确定当前学期，请使用 --term 指定，例如 2026-2027-1。")
    if not parsed.entries and not allow_empty:
        raise ScheduleBuildError("没有解析出课程；如确认这是空课表，可添加 --allow-empty。")

    incomplete = [entry for entry in parsed.entries if not entry.week_numbers]
    if incomplete and not allow_incomplete:
        names = "、".join(dict.fromkeys(entry.course_name for entry in incomplete[:3]))
        raise ScheduleBuildError(
            f"有 {len(incomplete)} 条课程没有识别出周次（例如：{names}）；"
            "请检查输入页面，或使用 --allow-incomplete 将它们放入“周次未识别”。"
        )

    entries = [_entry_payload(entry) for entry in parsed.entries]
    entries.sort(key=lambda item: (item["weekday"], item["block_start"], item["course_name"]))
    timestamp = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    warnings = [warning for warning in parsed.warnings if not (term and "--term" in warning)]

    return {
        "schema_version": 1,
        "generator": {
            "name": "cat-schedule-static",
            "version": __version__,
        },
        "generated_at": timestamp,
        "source": {
            "sha256": source_sha256,
            "encoding": parsed.source_encoding,
        },
        "page_title": title.strip() or "C.A.T. Schedule",
        "warnings": warnings,
        "schedule": {
            "term": resolved_term,
            "term_start_date": term_start_date,
            "available_terms": [resolved_term],
            "total_entries": len(entries),
            "entries": entries,
            "weeks": _build_weeks(entries, include_incomplete=allow_incomplete),
        },
    }
