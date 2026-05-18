"""Business logic for conversation management."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache_keys import chat_history_key
from app.core.exceptions import (
    ConversationNotFoundError,
    InvalidProviderModelError,
)
from app.core.llm_router import LLMRouter
from app.db.repositories.conversation_repo import ConversationRepository
from app.db.repositories.message_repo import MessageRepository
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import ConversationCreate
from app.services.cache_service import CacheService


class ConversationService:
    """Encapsulate conversation-related business operations."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        cache_service: CacheService,
    ) -> None:
        self.session = session
        self.cache_service = cache_service
        self.conversation_repo = ConversationRepository(session)
        self.message_repo = MessageRepository(session)

    async def create_conversation(
        self,
        *,
        user_id: str,
        payload: ConversationCreate,
    ) -> Conversation:
        """Create a new conversation for the user."""
        provider, model_name = self._resolve_provider_model(
            payload.provider or "",
            payload.model_name or "",
        )
        title = (
            payload.title.strip()
            if payload.title and payload.title.strip()
            else "New Chat"
        )
        conversation = await self.conversation_repo.create(
            user_id=user_id,
            title=title,
            provider=provider,
            model_name=model_name,
        )
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def list_conversations(
        self,
        *,
        user_id: str,
        skip: int,
        limit: int,
    ) -> tuple[list[Conversation], int]:
        """Return paginated conversations for the user."""
        conversations, total = await self.conversation_repo.list_for_user(
            user_id,
            skip=skip,
            limit=limit,
        )
        did_change = False
        for conversation in conversations:
            did_change |= self._canonicalize_conversation_model(conversation)

        if did_change:
            await self.session.commit()
        return conversations, total

    async def get_conversation_detail(
        self,
        *,
        user_id: str,
        conversation_id: uuid.UUID,
    ) -> tuple[Conversation, list[Message]]:
        """Return a conversation and its messages."""
        conversation = await self.conversation_repo.get_by_id_for_user(
            conversation_id,
            user_id,
        )
        if conversation is None:
            raise ConversationNotFoundError()

        if self._canonicalize_conversation_model(conversation):
            await self.session.commit()

        messages = await self.message_repo.list_for_conversation(conversation_id)
        return conversation, messages

    async def delete_conversation(
        self,
        *,
        user_id: str,
        conversation_id: uuid.UUID,
    ) -> None:
        """Soft-delete a conversation and clear its cache entry."""
        conversation = await self.conversation_repo.get_by_id_for_user(
            conversation_id,
            user_id,
        )
        if conversation is None:
            raise ConversationNotFoundError()

        await self.conversation_repo.soft_delete(conversation)
        await self.session.commit()
        await self.cache_service.delete(
            chat_history_key(conversation_id=str(conversation_id))
        )

    @staticmethod
    def _canonicalize_conversation_model(conversation: Conversation) -> bool:
        """Rewrite deprecated provider/model aliases in-place."""
        provider, model_name = ConversationService._resolve_provider_model(
            conversation.provider,
            conversation.model_name,
        )
        if conversation.provider == provider and conversation.model_name == model_name:
            return False

        conversation.provider = provider
        conversation.model_name = model_name
        return True

    @staticmethod
    def _resolve_provider_model(provider: str, model_name: str) -> tuple[str, str]:
        try:
            return LLMRouter.resolve_provider_model(provider, model_name)
        except ValueError as exc:
            msg = f"Unsupported model '{model_name}' for provider '{provider}'."
            raise InvalidProviderModelError(msg) from exc
