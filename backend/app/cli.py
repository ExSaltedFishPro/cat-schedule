from __future__ import annotations

import re

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

