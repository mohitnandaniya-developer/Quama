"""Remove obsolete Pinecone indexing state from user assets."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_remove_pinecone_asset_flag"
down_revision = "0007_add_broker_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop the unused Pinecone index flag."""
    with op.batch_alter_table("user_assets") as batch_op:
        batch_op.drop_column("pinecone_indexed")


def downgrade() -> None:
    """Restore the Pinecone index flag."""
    with op.batch_alter_table("user_assets") as batch_op:
        batch_op.add_column(
            sa.Column(
                "pinecone_indexed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
