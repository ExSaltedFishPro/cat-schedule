from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260407_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_invites_token_hash", "invites", ["token_hash"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("email_notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notification_email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True)

    op.create_table(
        "portal_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("portal_username", sa.String(length=100), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=False),
        sa.Column("encrypted_cookies", sa.Text(), nullable=True),
        sa.Column("cookie_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_schedule_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_grade_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_portal_accounts_user_id"),
    )

    op.create_table(
        "schedule_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term", sa.String(length=40), nullable=False),
        sa.Column("source_mode", sa.String(length=20), nullable=False),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("raw_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("entry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_schedule_snapshots_term", "schedule_snapshots", ["term"], unique=False)

    op.create_table(
        "schedule_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schedule_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term", sa.String(length=40), nullable=False),
        sa.Column("course_code", sa.String(length=64), nullable=True),
        sa.Column("class_no", sa.String(length=64), nullable=True),
        sa.Column("course_name", sa.String(length=255), nullable=False),
        sa.Column("teacher", sa.String(length=255), nullable=True),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("weekday_label", sa.String(length=20), nullable=False),
        sa.Column("block_start", sa.Integer(), nullable=False),
        sa.Column("block_end", sa.Integer(), nullable=False),
        sa.Column("block_label_start", sa.String(length=20), nullable=False),
        sa.Column("block_label_end", sa.String(length=20), nullable=False),
        sa.Column("time_text", sa.String(length=120), nullable=False),
        sa.Column("week_text", sa.String(length=120), nullable=False),
        sa.Column("week_numbers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("credit", sa.String(length=32), nullable=True),
        sa.Column("course_attribute", sa.String(length=80), nullable=True),
        sa.Column("selection_stage", sa.String(length=80), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    op.create_table(
        "grade_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_mode", sa.String(length=20), nullable=False),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "grade_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term", sa.String(length=40), nullable=False),
        sa.Column("record_key", sa.String(length=64), nullable=False),
        sa.Column("course_code", sa.String(length=64), nullable=True),
        sa.Column("course_name", sa.String(length=255), nullable=False),
        sa.Column("score", sa.String(length=40), nullable=True),
        sa.Column("score_numeric", sa.Numeric(6, 2), nullable=True),
        sa.Column("score_flag", sa.String(length=80), nullable=True),
        sa.Column("grade_point_text", sa.String(length=80), nullable=True),
        sa.Column("credit", sa.String(length=32), nullable=True),
        sa.Column("total_hours", sa.String(length=32), nullable=True),
        sa.Column("assessment_method", sa.String(length=80), nullable=True),
        sa.Column("course_attribute", sa.String(length=80), nullable=True),
        sa.Column("course_nature", sa.String(length=120), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "record_key", name="uq_grade_record_user_key"),
    )
    op.create_index("ix_grade_records_term", "grade_records", ["term"], unique=False)

    op.create_table(
        "grade_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grade_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grade_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_key", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("sent_to_email", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("notification_key", name="uq_grade_notification_key"),
    )

    op.create_table(
        "task_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_name", sa.String(length=80), nullable=False),
        sa.Column("queue_job_id", sa.String(length=80), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("task_logs")
    op.drop_table("grade_notifications")
    op.drop_index("ix_grade_records_term", table_name="grade_records")
    op.drop_table("grade_records")
    op.drop_table("grade_snapshots")
    op.drop_table("schedule_entries")
    op.drop_index("ix_schedule_snapshots_term", table_name="schedule_snapshots")
    op.drop_table("schedule_snapshots")
    op.drop_table("portal_accounts")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_invites_token_hash", table_name="invites")
    op.drop_table("invites")
