from __future__ import annotations

import json
import re
import secrets
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import User
from app.services.invite_service import create_invite, list_invites, revoke_invite
from app.services.task_service import enqueue_grade_check, enqueue_schedule_refresh


app = typer.Typer(help="C.A.T.课表管理 CLI")
console = Console()


def parse_duration_to_days(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d+)([dD])", value.strip())
    if not match:
        raise typer.BadParameter("仅支持类似 7d 这样的天数格式")
    return int(match.group(1))


def _load_notifications_file(path: Path) -> dict:
    if not path.exists():
        return {"version": "initial", "items": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"version": "imported", "items": payload}
    if not isinstance(payload, dict):
        raise typer.BadParameter("通知文件必须是 JSON 对象或数组")
    payload.setdefault("items", [])
    if not isinstance(payload["items"], list):
        raise typer.BadParameter("通知文件 items 必须是数组")
    return payload


def _write_notifications_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@app.command("create-invite")
def create_invite_command(
    max_uses: int | None = typer.Option(default=1, help="最大可使用次数"),
    expires_in: str | None = typer.Option(default="7d", help="过期时间，例如 7d"),
    note: str | None = typer.Option(default=None, help="备注"),
) -> None:
    expires_days = parse_duration_to_days(expires_in)
    with SessionLocal() as db:
        invite, token = create_invite(db, expires_in_days=expires_days, max_uses=max_uses, note=note)
    register_url = f"{settings.public_web_url.rstrip('/')}/register?invite={token}"
    console.print(f"[green]邀请已创建[/green] id={invite.id}")
    console.print(register_url)


@app.command("list-invites")
def list_invites_command() -> None:
    with SessionLocal() as db:
        invites = list_invites(db)
    table = Table(title="邀请链接列表")
    table.add_column("ID")
    table.add_column("状态")
    table.add_column("已用/上限")
    table.add_column("过期时间")
    table.add_column("备注")
    for invite in invites:
        status = "disabled" if invite.disabled else "active"
        limit_text = f"{invite.used_count}/{invite.max_uses or '∞'}"
        table.add_row(str(invite.id), status, limit_text, str(invite.expires_at or "-"), invite.note or "-")
    console.print(table)


@app.command("revoke-invite")
def revoke_invite_command(invite_id: str) -> None:
    with SessionLocal() as db:
        invite = revoke_invite(db, invite_id)
    console.print(f"[yellow]邀请已停用[/yellow] {invite.id}")


@app.command("add-notification")
def add_notification_command(
    title: str = typer.Option(..., "--title", help="通知标题"),
    body: str = typer.Option(..., "--body", help="通知正文"),
    level: str = typer.Option(default="info", help="通知级别：info / warning / error"),
    notification_id: str | None = typer.Option(None, "--id", help="通知 ID，不填则自动生成"),
) -> None:
    if level not in {"info", "warning", "error"}:
        raise typer.BadParameter("level 仅支持 info / warning / error")

    path = Path(settings.notifications_file_path)
    payload = _load_notifications_file(path)
    item_id = notification_id or f"notice-{secrets.token_hex(4)}"
    existing_ids = {str(item.get("id")) for item in payload["items"] if isinstance(item, dict)}
    if item_id in existing_ids:
        raise typer.BadParameter(f"通知 ID 已存在: {item_id}")

    payload["items"].append(
        {
            "id": item_id,
            "enabled": True,
            "level": level,
            "title": title,
            "body": body,
        }
    )
    payload["version"] = f"cli-{secrets.token_hex(6)}"
    _write_notifications_file(path, payload)
    console.print(f"[green]通知已添加[/green] id={item_id}")
    console.print(str(path))


@app.command("enqueue-schedule-refresh")
def enqueue_schedule_refresh_command(user_id: str, term: str | None = typer.Option(default=None)) -> None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            raise typer.BadParameter("用户不存在")
        task_log = enqueue_schedule_refresh(db, user=user, term=term)
    console.print(f"已入队课表刷新任务: {task_log.id} ({task_log.queue_job_id})")


@app.command("enqueue-grade-check")
def enqueue_grade_check_command(user_id: str) -> None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            raise typer.BadParameter("用户不存在")
        task_log = enqueue_grade_check(db, user=user)
    console.print(f"已入队成绩检查任务: {task_log.id} ({task_log.queue_job_id})")


if __name__ == "__main__":
    app()
