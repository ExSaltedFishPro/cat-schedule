from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from passlib.context import CryptContext


# 用 pbkdf2_sha256 避开 bcrypt 72-byte 限制，以及 passlib 1.7.4 与新 bcrypt 的兼容问题。
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    return datetime.now(UTC)


def expires_after(days: int) -> datetime:
    return utcnow() + timedelta(days=days)
