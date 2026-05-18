"""Message ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MessageRole(StrEnum):
    """Supported chat message roles."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(Base):
    """Persisted conversation message."""

    __tablename__ = "messages"
    __table_args__ = (
        Index(
            "ix_messages_conversation_created_at",
            "conversation_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        SqlEnum(MessageRole, name="message_role", native_enum=False)
    )
    content: Mapped[str] = mapped_column(Text())
    token_count: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    conversation = relationship("Conversation", back_populates="messages")
