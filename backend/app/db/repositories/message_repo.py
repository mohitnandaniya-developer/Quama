"""Message repository implementation."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.models.message import Message, MessageRole


class MessageRepository:
    """Encapsulate message persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        token_count: int | None = None,
    ) -> Message:
        """Create and flush a single message."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            token_count=token_count,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def list_for_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        """Return all messages for a conversation in ascending order."""
        stmt = (
            select(Message)
            .options(
                load_only(
                    Message.id,
                    Message.role,
                    Message.content,
                    Message.token_count,
                    Message.created_at,
                )
            )
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_recent_for_conversation(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int,
    ) -> list[Message]:
        """Return the most recent messages in ascending order."""
        stmt = (
            select(Message)
            .options(
                load_only(
                    Message.id,
                    Message.role,
                    Message.content,
                    Message.token_count,
                    Message.created_at,
                )
            )
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = (await self.session.execute(stmt)).scalars().all()
        return list(reversed(messages))
