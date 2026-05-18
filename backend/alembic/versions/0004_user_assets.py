"""Add permanent user asset storage."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_user_assets"
down_revision = "0003_architect_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create permanent user asset storage."""
    op.create_table(
        "user_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "file",
                "image",
                name="user_asset_kind",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
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
    )
    op.create_index("ix_user_assets_user_id", "user_assets", ["user_id"], unique=False)
    op.create_index(
        "ix_user_assets_user_created_at",
        "user_assets",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop permanent user asset storage."""
    op.drop_index("ix_user_assets_user_created_at", table_name="user_assets")
    op.drop_index("ix_user_assets_user_id", table_name="user_assets")
    op.drop_table("user_assets")
