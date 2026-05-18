"""Track Pinecone indexing state for user assets."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_user_asset_pinecone_indexed"
down_revision = "0004_user_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Pinecone index status to stored assets."""
    op.add_column(
        "user_assets",
        sa.Column(
            "pinecone_indexed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    """Remove Pinecone index status from stored assets."""
    op.drop_column("user_assets", "pinecone_indexed")
