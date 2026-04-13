from __future__ import annotations

from pydantic import BaseModel, EmailStr


class SettingsResponse(BaseModel):
    email_notifications_enabled: bool
    notification_email: EmailStr | None = None
    login_email: EmailStr
    display_name: str


class SettingsUpdateRequest(BaseModel):
    email_notifications_enabled: bool
    notification_email: EmailStr | None = None
