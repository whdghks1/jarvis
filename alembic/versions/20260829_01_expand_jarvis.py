"""Add profiles, conversations, messages, and memory lifecycle fields."""

from alembic import op
import sqlalchemy as sa

revision = "20260829_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "memories" not in tables:
        op.create_table(
            "memories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.String(100), nullable=False),
            sa.Column("type", sa.String(50), nullable=False),
            sa.Column("category", sa.String(100), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("normalized_key", sa.String(200), nullable=True),
            sa.Column("importance", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "normalized_key", name="uq_memory_user_key"),
        )
        op.create_index("ix_memories_user_id", "memories", ["user_id"])
    else:
        columns = {column["name"] for column in inspector.get_columns("memories")}
        if "normalized_key" not in columns:
            op.add_column("memories", sa.Column("normalized_key", sa.String(200), nullable=True))
        if "updated_at" not in columns:
            op.add_column(
                "memories",
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            )
        unique_names = {item["name"] for item in inspector.get_unique_constraints("memories")}
        if "uq_memory_user_key" not in unique_names:
            with op.batch_alter_table("memories") as batch_op:
                batch_op.create_unique_constraint(
                    "uq_memory_user_key", ["user_id", "normalized_key"]
                )

    if "user_profiles" not in tables:
        op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.String(100), primary_key=True),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("timezone", sa.String(100), nullable=False, server_default="Asia/Tokyo"),
        sa.Column("locale", sa.String(20), nullable=False, server_default="ko-KR"),
        sa.Column("preferred_language", sa.String(50), nullable=False, server_default="Korean"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    if "conversations" not in tables:
        op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
        op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    if "messages" not in tables:
        op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
        op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("user_profiles")
    op.drop_constraint("uq_memory_user_key", "memories", type_="unique")
    op.drop_column("memories", "updated_at")
    op.drop_column("memories", "normalized_key")
