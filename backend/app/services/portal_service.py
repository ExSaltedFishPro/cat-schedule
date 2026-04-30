from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.crypto import crypto_service
from app.core.errors import AppError
from app.core.security import utcnow
from app.models import PortalAccount, User
from app.portal.client import (
    PortalSessionExpiredError,
    build_portal_client,
    deserialize_cookies,
    serialize_cookies,
)
from app.portal.parsers import parse_exams_html, parse_grades_html, parse_lessons_html


logger = logging.getLogger(__name__)


def get_portal_account_summary(user: User) -> dict:
    account = user.portal_account
    if not account or not account.portal_username:
        return {
            "is_bound": False,
            "portal_username": None,
            "last_successful_login_at": None,
            "last_schedule_refresh_at": None,
            "last_grade_check_at": None,
            "last_failure_message": None,
            "has_reusable_cookie": False,
        }
    return {
        "is_bound": True,
        "portal_username": account.portal_username,
        "last_successful_login_at": account.last_successful_login_at,
        "last_schedule_refresh_at": account.last_schedule_refresh_at,
        "last_grade_check_at": account.last_grade_check_at,
        "last_failure_message": account.last_failure_message,
        "has_reusable_cookie": bool(account.encrypted_cookies),
    }


def save_portal_credentials(db: Session, *, user: User, portal_username: str, portal_password: str) -> PortalAccount:
    client = build_portal_client()
    login_result = client.login(portal_username=portal_username, portal_password=portal_password)
    account = user.portal_account or PortalAccount(user_id=user.id, portal_username=portal_username, encrypted_password="")
    account.portal_username = portal_username
    account.encrypted_password = crypto_service.encrypt(portal_password)
    account.encrypted_cookies = crypto_service.encrypt(serialize_cookies(login_result.cookies))
    account.cookie_expires_at = utcnow() + timedelta(days=7)
    account.last_successful_login_at = utcnow()
    account.last_failure_at = None
    account.last_failure_message = None
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _login_and_persist(db: Session, account: PortalAccount) -> dict[str, str]:
    client = build_portal_client()
    password = crypto_service.decrypt(account.encrypted_password)
    if not password:
        raise AppError(400, "PORTAL_ACCOUNT_INVALID", "教务账号密码不存在，请重新绑定")
    login_result = client.login(portal_username=account.portal_username, portal_password=password)
    account.encrypted_cookies = crypto_service.encrypt(serialize_cookies(login_result.cookies))
    account.cookie_expires_at = utcnow() + timedelta(days=7)
    account.last_successful_login_at = utcnow()
    account.last_failure_at = None
    account.last_failure_message = None
    db.commit()
    return login_result.cookies


def _load_cookies(account: PortalAccount) -> dict[str, str]:
    payload = crypto_service.decrypt(account.encrypted_cookies)
    return deserialize_cookies(payload)


def _fetch_with_auto_relogin(fetcher_name: str, db: Session, account: PortalAccount, **kwargs) -> tuple[str, dict[str, str]]:
    client = build_portal_client()
    cookies = _load_cookies(account) if account.encrypted_cookies else {}
    try:
        fetcher = getattr(client, fetcher_name)
        result = fetcher(cookies=cookies, **kwargs)
        return result.html, result.cookies
    except PortalSessionExpiredError:
        logger.info("Portal cookie expired for user %s, relogin now", account.user_id)
        cookies = _login_and_persist(db, account)
        fetcher = getattr(client, fetcher_name)
        result = fetcher(cookies=cookies, **kwargs)
        return result.html, result.cookies


def fetch_and_parse_schedule(db: Session, account: PortalAccount, *, term: str | None = None):
    if not account.portal_username:
        raise AppError(400, "PORTAL_ACCOUNT_REQUIRED", "请先绑定教务账号")
    html, cookies = _fetch_with_auto_relogin("fetch_lessons", db, account, term=term)
    account.encrypted_cookies = crypto_service.encrypt(serialize_cookies(cookies))
    account.last_schedule_refresh_at = utcnow()
    db.commit()
    return html, parse_lessons_html(html)


def fetch_and_parse_grades(db: Session, account: PortalAccount):
    if not account.portal_username:
        raise AppError(400, "PORTAL_ACCOUNT_REQUIRED", "请先绑定教务账号")
    html, cookies = _fetch_with_auto_relogin("fetch_grades", db, account)
    account.encrypted_cookies = crypto_service.encrypt(serialize_cookies(cookies))
    account.last_grade_check_at = utcnow()
    db.commit()
    return html, parse_grades_html(html)


def fetch_and_parse_exams(db: Session, account: PortalAccount):
    if not account.portal_username:
        raise AppError(400, "PORTAL_ACCOUNT_REQUIRED", "请先绑定教务账号")
    html, cookies = _fetch_with_auto_relogin("fetch_exams", db, account)
    account.encrypted_cookies = crypto_service.encrypt(serialize_cookies(cookies))
    db.commit()
    return html, parse_exams_html(html)
