from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class InviteVerifyRequest(BaseModel):
    invite_token: str = Field(min_length=10, max_length=255)


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    invite_token: str = Field(min_length=10, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class InvitePreview(BaseModel):
    valid: bool
    note: str | None = None
    expires_at: datetime | None = None
    remaining_uses: int | None = None

