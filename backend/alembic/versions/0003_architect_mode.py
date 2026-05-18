"""Add architect conversations and workspace assets."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_architect_mode"
down_revision = "0002_query_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply architect-mode schema additions."""
    op.add_column(
        "conversations",
        sa.Column(
            "mode",
            sa.Enum(
                "chat",
                "architect",
                name="conversation_mode",
                native_enum=False,
            ),
            nullable=False,
            server_default="chat",
        ),
    )
    op.add_column(
        "conversations",
        sa.Column("workspace_key", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_conversations_workspace_key",
        "conversations",
        ["workspace_key"],
        unique=False,
    )

    op.create_table(
        "workspace_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("workspace_key", sa.String(length=255), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column(
            "file_kind",
            sa.Enum(
                "file",
                "image",
                name="workspace_asset_kind",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("namespace", sa.String(length=255), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column(
            "ingest_status",
            sa.Enum(
                "ready",
                "failed",
                name="workspace_asset_status",
                native_enum=False,
            ),
            nullable=False,
            server_default="ready",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "workspace_key",
            "file_name",
            name="uq_workspace_assets_user_workspace_file",
        ),
    )
    op.create_index(
        "ix_workspace_assets_user_id",
        "workspace_assets",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_assets_workspace_key",
        "workspace_assets",
        ["workspace_key"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_assets_user_workspace_updated",
        "workspace_assets",
        ["user_id", "workspace_key", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_assets_namespace_status",
        "workspace_assets",
        ["namespace", "ingest_status"],
        unique=False,
    )


def downgrade() -> None:
    """Remove architect-mode schema additions."""
    op.drop_index(
        "ix_workspace_assets_namespace_status",
        table_name="workspace_assets",
    )
    op.drop_index(
        "ix_workspace_assets_user_workspace_updated",
        table_name="workspace_assets",
    )
    op.drop_index("ix_workspace_assets_workspace_key", table_name="workspace_assets")
    op.drop_index("ix_workspace_assets_user_id", table_name="workspace_assets")
    op.drop_table("workspace_assets")

    op.drop_index("ix_conversations_workspace_key", table_name="conversations")
    op.drop_column("conversations", "workspace_key")
    op.drop_column("conversations", "mode")
