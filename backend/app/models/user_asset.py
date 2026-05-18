"""Persistent user asset ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserAssetKind(StrEnum):
    """Supported stored asset kinds."""

    FILE = "file"
    IMAGE = "image"


class UserAsset(Base):
    """Persisted metadata for permanent user assets."""

    __tablename__ = "user_assets"
    __table_args__ = (
        Index("ix_user_assets_user_id", "user_id"),
        Index("ix_user_assets_user_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[UserAssetKind] = mapped_column(
        SqlEnum(UserAssetKind, name="user_asset_kind", native_enum=False)
    )
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer(), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text(), nullable=False)
    pinecone_indexed: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=False,
        server_default="false",
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
