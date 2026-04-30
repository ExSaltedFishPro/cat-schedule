from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests

from app.core.config import settings
from app.core.errors import AppError
from app.portal.captcha import build_captcha_solver
from app.portal.parsers import extract_login_error, is_login_page, parse_login_form


logger = logging.getLogger(__name__)


class PortalSessionExpiredError(Exception):
    pass


@dataclass
class PortalLoginResult:
    cookies: dict[str, str]


@dataclass
class PortalPageResult:
    html: str
    cookies: dict[str, str]


def decode_response(response: requests.Response) -> str:
    response.encoding = response.encoding or response.apparent_encoding or "utf-8"
    return response.text


def current_academic_term(now: datetime | None = None) -> str:
    value = now or datetime.now()
    if value.month >= 8:
        return f"{value.year}-{value.year + 1}-1"
    if value.month >= 2:
        return f"{value.year - 1}-{value.year}-2"
    return f"{value.year - 1}-{value.year}-1"


class BasePortalClient:
    def login(self, portal_username: str, portal_password: str) -> PortalLoginResult:
        raise NotImplementedError

    def fetch_lessons(self, cookies: dict[str, str], term: str | None = None) -> PortalPageResult:
        raise NotImplementedError

    def fetch_grades(self, cookies: dict[str, str]) -> PortalPageResult:
        raise NotImplementedError

    def fetch_exams(self, cookies: dict[str, str]) -> PortalPageResult:
        raise NotImplementedError


class SamplePortalClient(BasePortalClient):
    def __init__(self, sample_dir: Path) -> None:
        self.sample_dir = sample_dir

    def _read_file(self, name: str) -> str:
        path = self.sample_dir / name
        if not path.is_file():
            raise AppError(500, "SAMPLE_HTML_NOT_FOUND", f"示例 HTML 不存在: {path}")
        return path.read_text(encoding="utf-8")

    def login(self, portal_username: str, portal_password: str) -> PortalLoginResult:
        parse_login_form(self._read_file("login.html"))
        if not portal_username or not portal_password:
            raise AppError(400, "PORTAL_LOGIN_FAILED", "示例模式下也需要提供教务账号和密码")
        return PortalLoginResult(cookies={"JSESSIONID": "sample-session-id"})

    def fetch_lessons(self, cookies: dict[str, str], term: str | None = None) -> PortalPageResult:
        if not cookies.get("JSESSIONID"):
            raise PortalSessionExpiredError("missing sample session")
        return PortalPageResult(html=self._read_file("lessons.html"), cookies=cookies)

    def fetch_grades(self, cookies: dict[str, str]) -> PortalPageResult:
        if not cookies.get("JSESSIONID"):
            raise PortalSessionExpiredError("missing sample session")
        return PortalPageResult(html=self._read_file("grades.html"), cookies=cookies)

    def fetch_exams(self, cookies: dict[str, str]) -> PortalPageResult:
        if not cookies.get("JSESSIONID"):
            raise PortalSessionExpiredError("missing sample session")
        return PortalPageResult(html=self._read_file("考试查询.txt"), cookies=cookies)


class RealPortalClient(BasePortalClient):
    def __init__(self) -> None:
        self.base_url = settings.portal_base_url.rstrip("/")
        self.login_base_url = (settings.portal_login_base_url or settings.portal_base_url).rstrip("/")
        self.timeout = settings.portal_request_timeout_seconds
        self.captcha_solver = build_captcha_solver()

    def _session(self, cookies: dict[str, str] | None = None) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            }
        )
        if cookies:
            session.cookies.update(cookies)
        return session

    def _assert_not_login_page(self, html: str) -> None:
        if is_login_page(html):
            raise PortalSessionExpiredError("portal session expired")

    def _looks_like_credential_error(self, message: str | None) -> bool:
        message = (message or "").lower()
        if not message:
            return False
        if "captcha" in message or "验证码" in message or "校验码" in message or "随机码" in message:
            return False
        return any(token in message for token in ["密码", "账号", "帐户", "用户名", "user"])

    def _origin_for(self, url: str) -> str:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}"

    def _append_cache_buster(self, url: str) -> str:
        parts = urlsplit(url)
        query = parse_qsl(parts.query, keep_blank_values=True)
        query.append(("t", secrets.token_hex(8)))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    def login(self, portal_username: str, portal_password: str) -> PortalLoginResult:
        login_url = urljoin(self.login_base_url + "/", settings.portal_login_path.lstrip("/"))
        last_message = "教务系统登录失败，请检查账号、密码或验证码识别"

        for attempt in range(1, settings.portal_captcha_max_attempts + 1):
            session = self._session()
            response = session.get(login_url, timeout=self.timeout)
            html = decode_response(response)
            form = parse_login_form(html)
            logger.info(
                "Portal login form detected: method=%s action=%s username_field=%s password_field=%s captcha_field=%s hidden_field_count=%s",
                form.method,
                form.action,
                form.username_field,
                form.password_field,
                form.captcha_field,
                len(form.hidden_fields),
            )

            captcha_value = ""
            if form.captcha_image_url:
                captcha_url = self._append_cache_buster(urljoin(response.url, form.captcha_image_url))
                captcha_response = session.get(
                    captcha_url,
                    timeout=self.timeout,
                    headers={
                        "Referer": response.url,
                        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                    },
                )
                solved = self.captcha_solver.solve(captcha_response.content)
                captcha_value = solved.code
                logger.info(
                    "Captcha solved on attempt %s/%s with confidence %.2f",
                    attempt,
                    settings.portal_captcha_max_attempts,
                    solved.confidence,
                )

            payload = {**form.hidden_fields}
            payload[form.username_field] = portal_username
            payload[form.password_field] = portal_password
            payload[form.captcha_field] = captcha_value

            post_url = urljoin(response.url, form.action)
            login_response = session.request(
                form.method,
                post_url,
                data=payload,
                timeout=self.timeout,
                allow_redirects=True,
                headers={
                    "Referer": response.url,
                    "Origin": self._origin_for(response.url),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            login_html = decode_response(login_response)
            if not is_login_page(login_html):
                cookies = requests.utils.dict_from_cookiejar(session.cookies)
                if "JSESSIONID" not in cookies:
                    raise AppError(400, "PORTAL_LOGIN_FAILED", "未获取到教务系统会话 Cookie (JSESSIONID)")
                return PortalLoginResult(cookies=cookies)

            last_message = extract_login_error(login_html) or "教务系统登录失败，请检查账号、密码或验证码识别"
            if self._looks_like_credential_error(last_message):
                raise AppError(400, "PORTAL_LOGIN_FAILED", last_message)
            if attempt < settings.portal_captcha_max_attempts:
                logger.warning(
                    "Portal login failed on attempt %s/%s, retrying. status=%s final_url=%s message=%s",
                    attempt,
                    settings.portal_captcha_max_attempts,
                    login_response.status_code,
                    login_response.url,
                    last_message,
                )

        raise AppError(400, "PORTAL_LOGIN_FAILED", last_message)

    def fetch_lessons(self, cookies: dict[str, str], term: str | None = None) -> PortalPageResult:
        session = self._session(cookies)
        url = urljoin(self.base_url + "/", settings.portal_lessons_path.lstrip("/"))
        response = session.get(url, params={"xnxq01id": term} if term else None, timeout=self.timeout)
        html = decode_response(response)
        self._assert_not_login_page(html)
        return PortalPageResult(html=html, cookies=requests.utils.dict_from_cookiejar(session.cookies))

    def fetch_grades(self, cookies: dict[str, str]) -> PortalPageResult:
        session = self._session(cookies)
        url = urljoin(self.base_url + "/", settings.portal_grades_path.lstrip("/"))
        response = session.post(
            url,
            data={
                "kksj": "",
                "kcxz": "",
                "kcmc": "",
                "xsfs": "max",
            },
            timeout=self.timeout,
            headers={
                "Referer": url,
                "Origin": self._origin_for(url),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        html = decode_response(response)
        self._assert_not_login_page(html)
        return PortalPageResult(html=html, cookies=requests.utils.dict_from_cookiejar(session.cookies))

    def fetch_exams(self, cookies: dict[str, str]) -> PortalPageResult:
        session = self._session(cookies)
        url = urljoin(self.base_url + "/", settings.portal_exams_path.lstrip("/"))
        referer = urljoin(self.base_url + "/", settings.portal_exams_path.replace("_list", "_query").lstrip("/"))
        response = session.post(
            url,
            data={"xnxqid": current_academic_term()},
            timeout=self.timeout,
            headers={
                "Referer": referer,
                "Origin": self._origin_for(url),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        html = decode_response(response)
        self._assert_not_login_page(html)
        return PortalPageResult(html=html, cookies=requests.utils.dict_from_cookiejar(session.cookies))


def build_portal_client() -> BasePortalClient:
    if settings.portal_mode == "sample":
        return SamplePortalClient(settings.portal_sample_path)
    return RealPortalClient()


def serialize_cookies(cookies: dict[str, str]) -> str:
    return json.dumps(cookies, ensure_ascii=False)


def deserialize_cookies(payload: str | None) -> dict[str, str]:
    if not payload:
        return {}
    return json.loads(payload)
