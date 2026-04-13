from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import expires_after, generate_token, hash_password, hash_token, utcnow, verify_password
from app.models import AuthSession, User
from app.services.invite_service import consume_invite, validate_invite_token


def register_user(
    db: Session,
    *,
    display_name: str,
    email: str,
    password: str,
    invite_token: str,
) -> User:
    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user:
        raise AppError(400, "EMAIL_ALREADY_REGISTERED", "该邮箱已注册")

    invite = validate_invite_token(db, invite_token)
    user = User(
        display_name=display_name,
        email=email,
        password_hash=hash_password(password),
        notification_email=email,
    )
    consume_invite(invite)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(password, user.password_hash):
        raise AppError(401, "INVALID_CREDENTIALS", "邮箱或密码不正确")
    return user


def create_auth_session(db: Session, *, user: User, session_days: int) -> tuple[AuthSession, str]:
    raw_token = generate_token(32)
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=expires_after(session_days),
        last_seen_at=utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, raw_token


def get_user_by_session_token(db: Session, raw_token: str | None) -> User:
    if not raw_token:
        raise AppError(401, "UNAUTHORIZED", "请先登录")
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(raw_token)))
    if not session or session.revoked_at is not None or session.expires_at <= utcnow():
        raise AppError(401, "UNAUTHORIZED", "登录状态已失效，请重新登录")
    session.last_seen_at = utcnow()
    user = db.get(User, session.user_id)
    if not user:
        raise AppError(401, "UNAUTHORIZED", "登录状态已失效，请重新登录")
    db.commit()
    return user


def revoke_session(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(raw_token)))
    if not session:
        return
    session.revoked_at = utcnow()
    db.commit()

