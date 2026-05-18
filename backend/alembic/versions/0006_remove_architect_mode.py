"""Remove architect-specific schema."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_remove_architect_mode"
down_revision = "0005_user_asset_pinecone_indexed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop architect-only tables and conversation columns."""
    op.execute(sa.text("DELETE FROM conversations WHERE mode = 'architect'"))

    op.drop_index(
        "ix_workspace_assets_namespace_status",
        table_name="workspace_assets",
        if_exists=True,
    )
    op.drop_index(
        "ix_workspace_assets_user_workspace_updated",
        table_name="workspace_assets",
        if_exists=True,
    )
    op.drop_index(
        "ix_workspace_assets_workspace_key",
        table_name="workspace_assets",
        if_exists=True,
    )
    op.drop_index(
        "ix_workspace_assets_user_id",
        table_name="workspace_assets",
        if_exists=True,
    )
    op.drop_table("workspace_assets", if_exists=True)

    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_index("ix_conversations_workspace_key")
        batch_op.drop_column("workspace_key")
        batch_op.drop_column("mode")


def downgrade() -> None:
    """Recreate architect-only schema."""
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.add_column(
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
            )
        )
        batch_op.add_column(
            sa.Column("workspace_key", sa.String(length=255), nullable=True)
        )
        batch_op.create_index(
            "ix_conversations_workspace_key",
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
