from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.errors import api_success
from app.db.session import get_db
from app.models import User
from app.schemas.auth import InviteVerifyRequest, LoginRequest, RegisterRequest
from app.services.auth_service import authenticate_user, create_auth_session, register_user, revoke_session
from app.services.invite_service import invite_preview, validate_invite_token


router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.session_secure_cookie,
        max_age=settings.session_days * 24 * 3600,
    )


@router.post("/invite/verify")
def verify_invite(payload: InviteVerifyRequest, db: Session = Depends(get_db)) -> dict:
    invite = validate_invite_token(db, payload.invite_token)
    return api_success(invite_preview(invite), message="邀请链接有效")


@router.post("/register")
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    user = register_user(
        db,
        display_name=payload.display_name,
        email=payload.email,
        password=payload.password,
        invite_token=payload.invite_token,
    )
    _, token = create_auth_session(db, user=user, session_days=settings.session_days)
    _set_session_cookie(response, token)
    return api_success(
        {"user": {"id": str(user.id), "display_name": user.display_name, "email": user.email}},
        message="注册成功",
    )


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    user = authenticate_user(db, email=payload.email, password=payload.password)
    _, token = create_auth_session(db, user=user, session_days=settings.session_days)
    _set_session_cookie(response, token)
    return api_success(
        {"user": {"id": str(user.id), "display_name": user.display_name, "email": user.email}},
        message="登录成功",
    )


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return api_success(
        {"user": {"id": str(current_user.id), "display_name": current_user.display_name, "email": current_user.email}}
    )


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> dict:
    revoke_session(db, session_token)
    response.delete_cookie(settings.session_cookie_name)
    return api_success(message="已退出登录")

