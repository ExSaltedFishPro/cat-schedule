from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import generate_token, hash_token, utcnow
from app.models import Invite


def remaining_uses(invite: Invite) -> int | None:
    if invite.max_uses is None:
        return None
    return max(invite.max_uses - invite.used_count, 0)


def is_invite_usable(invite: Invite) -> bool:
    if invite.disabled:
        return False
    if invite.expires_at and invite.expires_at <= utcnow():
        return False
    if invite.max_uses is not None and invite.used_count >= invite.max_uses:
        return False
    return True


def create_invite(
    db: Session,
    *,
    expires_in_days: int | None,
    max_uses: int | None,
    note: str | None,
) -> tuple[Invite, str]:
    token = generate_token(24)
    invite = Invite(
        token_hash=hash_token(token),
        expires_at=utcnow() + timedelta(days=expires_in_days) if expires_in_days else None,
        max_uses=max_uses,
        note=note,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite, token


def list_invites(db: Session) -> list[Invite]:
    return list(db.scalars(select(Invite).order_by(Invite.created_at.desc())))


def revoke_invite(db: Session, invite_id: str) -> Invite:
    invite = db.get(Invite, invite_id)
    if not invite:
        raise AppError(404, "INVITE_NOT_FOUND", "邀请链接不存在")
    invite.disabled = True
    db.commit()
    db.refresh(invite)
    return invite


def validate_invite_token(db: Session, token: str) -> Invite:
    invite = db.scalar(select(Invite).where(Invite.token_hash == hash_token(token)))
    if not invite or not is_invite_usable(invite):
        raise AppError(400, "INVALID_INVITE", "邀请链接无效、已过期或已被停用")
    return invite


def consume_invite(invite: Invite) -> None:
    invite.used_count += 1


def invite_preview(invite: Invite) -> dict:
    return {
        "valid": True,
        "note": invite.note,
        "expires_at": invite.expires_at,
        "remaining_uses": remaining_uses(invite),
    }

