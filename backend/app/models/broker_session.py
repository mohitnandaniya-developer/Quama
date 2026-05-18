"""Persistent broker session ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BrokerSession(Base):
    """Persisted broker authentication/session metadata."""

    __tablename__ = "broker_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "broker", name="uq_broker_sessions_user_broker"),
        Index(
            "ix_broker_sessions_user_broker_active", "user_id", "broker", "is_active"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    broker: Mapped[str] = mapped_column(String(50), nullable=False)
    client_code: Mapped[str] = mapped_column(String(255), nullable=False)
    jwt_token: Mapped[str] = mapped_column(Text(), nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text(), nullable=False)
    feed_token: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=True,
        server_default="true",
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    token_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
