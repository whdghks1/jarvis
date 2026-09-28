"""Add assistant/creative mode to conversations."""

from alembic import op
import sqlalchemy as sa

revision = "20260928_03"
down_revision = "20260830_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "mode",
            sa.String(length=20),
            nullable=False,
            server_default="assistant",
        ),
    )
    op.create_index("ix_conversations_mode", "conversations", ["mode"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_conversations_mode", table_name="conversations")
    op.drop_column("conversations", "mode")
