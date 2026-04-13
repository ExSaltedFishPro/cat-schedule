from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import api_success
from app.db.session import get_db
from app.models import User
from app.schemas.settings import SettingsUpdateRequest


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(current_user: User = Depends(get_current_user)) -> dict:
    return api_success(
        {
            "email_notifications_enabled": current_user.email_notifications_enabled,
            "notification_email": current_user.notification_email or current_user.email,
            "login_email": current_user.email,
            "display_name": current_user.display_name,
        }
    )


@router.post("")
def update_settings(
    payload: SettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    current_user.email_notifications_enabled = payload.email_notifications_enabled
    current_user.notification_email = payload.notification_email or current_user.email
    db.commit()
    db.refresh(current_user)
    return api_success(
        {
            "email_notifications_enabled": current_user.email_notifications_enabled,
            "notification_email": current_user.notification_email,
            "login_email": current_user.email,
            "display_name": current_user.display_name,
        },
        message="设置已保存",
    )

