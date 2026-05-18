"""Add composite indexes for conversation and message lookups."""

from __future__ import annotations

from alembic import op

revision = "0002_query_indexes"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply composite indexes used by the hottest read paths."""
    op.create_index(
        "ix_conversations_user_deleted_updated_created",
        "conversations",
        ["user_id", "deleted_at", "updated_at", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_messages_conversation_created_at",
        "messages",
        ["conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove composite query indexes."""
    op.drop_index("ix_messages_conversation_created_at", table_name="messages")
    op.drop_index(
        "ix_conversations_user_deleted_updated_created",
        table_name="conversations",
    )
