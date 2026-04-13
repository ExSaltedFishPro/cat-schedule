from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "猫咪课表"
    app_env: str = "development"
    debug: bool = True
    api_base_path: str = "/api"
    public_web_url: str = "http://localhost:5173"
    api_cors_origins: list[str] | str = Field(default_factory=lambda: ["http://localhost:5173"])

    database_url: str = "postgresql+psycopg://cat_schedule:cat_schedule@localhost:5432/cat_schedule"
    redis_url: str = "redis://localhost:6379/0"

    session_cookie_name: str = "cat_schedule_session"
    session_days: int = 45
    session_secure_cookie: bool = False

    app_secret_key: str | None = None
    data_encryption_key: str | None = None

    resend_api_key: str | None = None
    resend_from_email: str = "Cat Schedule <noreply@example.com>"

    portal_mode: str = "sample"
    portal_base_url: str = "https://example.edu.cn"
    portal_login_path: str = "/"
    portal_lessons_path: str = "/xskb/xskb_list.do"
    portal_grades_path: str = "/kscj/cjcx_list"
    portal_request_timeout_seconds: int = 20
    portal_sample_dir: str = "../"
    portal_captcha_solver: str = "auto"
    portal_captcha_expected_length: int | None = None
    portal_captcha_charset: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    portal_captcha_max_attempts: int = 3
    portal_fixed_captcha: str | None = None

    grade_check_interval_minutes: int = 180
    scheduler_timezone: str = "Asia/Hong_Kong"

    queue_name: str = "cat_schedule"

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @cached_property
    def app_secret_key_value(self) -> str:
        value = (self.app_secret_key or "").strip()
        if not value:
            raise RuntimeError("APP_SECRET_KEY is required")
        return value

    @cached_property
    def data_encryption_key_value(self) -> str:
        value = (self.data_encryption_key or "").strip()
        if not value:
            raise RuntimeError("DATA_ENCRYPTION_KEY is required")
        return value

    @cached_property
    def resend_api_key_value(self) -> str | None:
        value = (self.resend_api_key or "").strip()
        return value or None

    @cached_property
    def portal_sample_path(self) -> Path:
        return Path(self.portal_sample_dir).resolve()


settings = Settings()
