"""Conversation repository implementation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.models.conversation import Conversation


class ConversationRepository:
    """Encapsulate conversation persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: str,
        title: str,
        provider: str,
        model_name: str,
    ) -> Conversation:
        """Create and flush a new conversation."""
        conversation = Conversation(
            user_id=user_id,
            title=title,
            provider=provider,
            model_name=model_name,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get_by_id_for_user(
        self,
        conversation_id: uuid.UUID,
        user_id: str,
        *,
        include_deleted: bool = False,
    ) -> Conversation | None:
        """Return a conversation owned by the user."""
        stmt = (
            select(Conversation)
            .options(
                load_only(
                    Conversation.id,
                    Conversation.user_id,
                    Conversation.title,
                    Conversation.provider,
                    Conversation.model_name,
                    Conversation.created_at,
                    Conversation.updated_at,
                    Conversation.deleted_at,
                )
            )
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        if not include_deleted:
            stmt = stmt.where(Conversation.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: str,
        *,
        skip: int,
        limit: int,
    ) -> tuple[list[Conversation], int]:
        """Return paginated active conversations and the total count."""
        total_stmt = (
            select(func.count())
            .select_from(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.deleted_at.is_(None),
            )
        )
        total = await self.session.scalar(total_stmt)

        items_stmt = (
            select(Conversation)
            .options(
                load_only(
                    Conversation.id,
                    Conversation.user_id,
                    Conversation.title,
                    Conversation.provider,
                    Conversation.model_name,
                    Conversation.created_at,
                    Conversation.updated_at,
                )
            )
            .where(
                Conversation.user_id == user_id,
                Conversation.deleted_at.is_(None),
            )
            .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = (await self.session.execute(items_stmt)).scalars().all()
        return items, int(total or 0)

    async def soft_delete(self, conversation: Conversation) -> Conversation:
        """Soft-delete a conversation."""
        now = datetime.now(UTC)
        conversation.deleted_at = now
        conversation.updated_at = now
        await self.session.flush()
        return conversation

    async def touch(self, conversation: Conversation) -> Conversation:
        """Update the conversation timestamp."""
        conversation.updated_at = datetime.now(UTC)
        await self.session.flush()
        return conversation
