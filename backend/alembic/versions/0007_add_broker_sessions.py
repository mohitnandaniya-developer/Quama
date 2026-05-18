"""Add broker sessions."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_add_broker_sessions"
down_revision = "0006_remove_architect_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create broker session persistence."""
    op.create_table(
        "broker_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("broker", sa.String(length=50), nullable=False),
        sa.Column("client_code", sa.String(length=255), nullable=False),
        sa.Column("jwt_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("feed_token", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("token_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "broker", name="uq_broker_sessions_user_broker"),
    )
    op.create_index(
        "ix_broker_sessions_user_id",
        "broker_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_broker_sessions_user_broker_active",
        "broker_sessions",
        ["user_id", "broker", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    """Drop broker session persistence."""
    op.drop_index("ix_broker_sessions_user_broker_active", table_name="broker_sessions")
    op.drop_index("ix_broker_sessions_user_id", table_name="broker_sessions")
    op.drop_table("broker_sessions")
