from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.errors import api_success
from app.core.security import utcnow
from app.models import User


router = APIRouter(prefix="/notifications", tags=["notifications"])


def _parse_datetime(value: Any):
    if not value:
        return None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _is_active(item: dict[str, Any]) -> bool:
    if item.get("enabled") is False:
        return False
    now = utcnow()
    starts_at = _parse_datetime(item.get("starts_at"))
    ends_at = _parse_datetime(item.get("ends_at"))
    if starts_at and starts_at > now:
        return False
    if ends_at and ends_at <= now:
        return False
    return True


def _normalize_item(item: dict[str, Any], index: int) -> dict[str, Any] | None:
    title = str(item.get("title") or "").strip()
    body = str(item.get("body") or item.get("message") or "").strip()
    if not title and not body:
        return None
    fingerprint_source = json.dumps(
        {
            "title": title,
            "body": body,
            "level": item.get("level") or "info",
            "created_at": item.get("created_at"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    item_id = str(item.get("id") or hashlib.sha256(f"{title}|{body}|{index}".encode("utf-8")).hexdigest()[:16])
    return {
        "id": item_id,
        "fingerprint": hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:16],
        "title": title or "通知",
        "body": body,
        "level": str(item.get("level") or "info"),
        "created_at": item.get("created_at"),
    }


@router.get("")
def list_notifications(_: User = Depends(get_current_user)) -> dict:
    path = Path(settings.notifications_file_path)
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"version": "initial", "items": []}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return api_success({"version": "empty", "items": []})

    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    if isinstance(payload, list):
        version = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        raw_items = payload
    else:
        version = str(payload.get("version") or hashlib.sha256(raw.encode("utf-8")).hexdigest())
        raw_items = payload.get("items") or []

    items = []
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict) or not _is_active(item):
            continue
        normalized = _normalize_item(item, index)
        if normalized:
            items.append(normalized)

    return api_success({"version": version, "items": items})
