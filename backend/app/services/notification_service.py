from __future__ import annotations

import logging

import requests

from app.core.config import settings
from app.core.errors import AppError


logger = logging.getLogger(__name__)


def send_grade_notification_email(*, to_email: str, subject: str, html_body: str) -> None:
    if not settings.resend_api_key_value:
        logger.warning("Resend API key not configured, skip email delivery to %s", to_email)
        return
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key_value}",
            "Content-Type": "application/json",
        },
        json={
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise AppError(502, "EMAIL_SEND_FAILED", f"Resend 发信失败: {response.text}")

