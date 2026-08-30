"""Add paired devices, pending actions, and action audit logs."""

from alembic import op
import sqlalchemy as sa

revision = "20260830_02"
down_revision = "20260829_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_devices_token_hash", "devices", ["token_hash"], unique=True)
    op.create_table(
        "pending_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_confirmation"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("requested_by_device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pending_actions_action_type", "pending_actions", ["action_type"])
    op.create_index("ix_pending_actions_status", "pending_actions", ["status"])
    op.create_table(
        "action_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action_id", sa.Integer(), sa.ForeignKey("pending_actions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("detail", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_action_audit_logs_action_id", "action_audit_logs", ["action_id"])


def downgrade() -> None:
    op.drop_table("action_audit_logs")
    op.drop_table("pending_actions")
    op.drop_table("devices")
