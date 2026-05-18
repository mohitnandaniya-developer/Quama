"""Business logic for chat messaging."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, ClassVar

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.cache_keys import chat_history_key
from app.core.exceptions import (
    ConversationNotFoundError,
    InvalidProviderModelError,
    ProviderRequestError,
)
from app.core.llm_factory import LLMFactory
from app.core.llm_router import LLMRouter
from app.core.message_content import (
    encode_user_message_content,
    serialize_message_for_history,
)
from app.db.repositories.conversation_repo import ConversationRepository
from app.db.repositories.message_repo import MessageRepository
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole
from app.schemas.chat import ChatAttachmentRequest, ChatMessageResponse
from app.services.cache_service import CacheService
from app.services.mcp.newsapi_mcp_client import ALLOWED_NEWSAPI_TOOLS
from app.services.mcp_connection_service import MCPConnectionService
from app.services.pinecone_service import PineconeService
from app.services.portfolio_sync_service import PortfolioSyncService

logger = logging.getLogger(__name__)

SYSTEM_SCRATCHPAD_PROMPT = (
    "You are Quama, an agentic AI assistant. You have access to the user's "
    "uploaded knowledge base via RAG retrieval. Think step by step. If a task "
    "requires multiple steps, outline your plan briefly before executing."
)
MEMORY_SUMMARY_PROVIDER = "groq"
MEMORY_SUMMARY_MODEL = "llama-3.1-8b-instant"
DEFAULT_CHAT_HISTORY_CACHE_TTL_SECONDS = 3600


class ChatService:
    """Encapsulate chat send and stream operations."""

    history_limit = 20
    cache_ttl_seconds = DEFAULT_CHAT_HISTORY_CACHE_TTL_SECONDS
    memory_summary_window = 10
    _conversation_locks: ClassVar[dict[uuid.UUID, asyncio.Lock]] = {}

    def __init__(
        self,
        *,
        session: AsyncSession,
        cache_service: CacheService,
        pinecone_service: PineconeService,
        portfolio_sync_service: PortfolioSyncService,
        settings: Settings,
        groww_broker_service: Any | None = None,
        history_cache_ttl_seconds: int = DEFAULT_CHAT_HISTORY_CACHE_TTL_SECONDS,
    ) -> None:
        self.session = session
        self.cache_service = cache_service
        self.pinecone_service = pinecone_service
        self.portfolio_sync_service = portfolio_sync_service
        self.settings = settings
        self.groww_broker_service = groww_broker_service
        self.cache_ttl_seconds = max(int(history_cache_ttl_seconds), 1)
        self.conversation_repo = ConversationRepository(session)
        self.message_repo = MessageRepository(session)

    async def send_message(
        self,
        *,
        user_id: str,
        conversation_id: uuid.UUID,
        user_message: str,
        provider: str | None,
        model_name: str | None,
        attachments: list[ChatAttachmentRequest],
    ) -> ChatMessageResponse:
        """Send a user message to the configured model and persist the exchange."""
        async with self._conversation_lock(conversation_id):
            conversation = await self._get_conversation(user_id, conversation_id)
            conversation = await self._apply_requested_model(
                conversation,
                provider=provider,
                model_name=model_name,
            )
            history = await self._load_history(conversation_id)
            normalized_attachments = self._normalize_attachments(attachments)
            self._ensure_image_attachments_supported(
                conversation.provider,
                normalized_attachments,
            )
            llm = self._get_llm(conversation.provider, conversation.model_name)
            knowledge_context = await self._safe_retrieve_knowledge_context(
                user_message=user_message,
                user_id=user_id,
            )
            memory_context = await self._safe_retrieve_memory_context(
                user_message=user_message,
                user_id=user_id,
            )
            portfolio_context = await self._safe_retrieve_portfolio_context(
                user_id=user_id,
            )
            news_context = await self._safe_retrieve_news_context(
                user_id=user_id,
                user_message=user_message,
            )
            llm_messages = self._build_langchain_messages(
                history,
                user_message,
                normalized_attachments,
                provider=conversation.provider,
                knowledge_context=knowledge_context,
                memory_context=memory_context,
                portfolio_context=portfolio_context,
                news_context=news_context,
            )

            try:
                response = await llm.ainvoke(llm_messages)
            except Exception as exc:
                logger.exception(
                    "Provider request failed for conversation %s.",
                    conversation_id,
                )
                raise ProviderRequestError() from exc

            assistant_content = self._extract_text(
                getattr(response, "content", response)
            )
            token_count = self._extract_token_count(response)
            assistant_record, _ = await self._persist_exchange(
                conversation=conversation,
                history=history,
                user_message=user_message,
                attachments=self._attachments_for_storage(normalized_attachments),
                assistant_content=assistant_content,
                token_count=token_count,
            )
            await self._maybe_store_conversation_memory(
                conversation=conversation,
                user_id=user_id,
            )

        return ChatMessageResponse(
            message_id=assistant_record.id,
            role=assistant_record.role.value,
            content=assistant_record.content,
            created_at=assistant_record.created_at,
            token_count=assistant_record.token_count,
        )

    async def stream_message(
        self,
        *,
        user_id: str,
        conversation_id: uuid.UUID,
        user_message: str,
        provider: str | None,
        model_name: str | None,
        attachments: list[ChatAttachmentRequest],
    ) -> AsyncIterator[str]:
        """Stream an assistant response as SSE chunks and persist on completion."""
        lock = self._get_lock(conversation_id)
        await lock.acquire()

        try:
            conversation = await self._get_conversation(user_id, conversation_id)
            conversation = await self._apply_requested_model(
                conversation,
                provider=provider,
                model_name=model_name,
            )
            history = await self._load_history(conversation_id)
            normalized_attachments = self._normalize_attachments(attachments)
            self._ensure_image_attachments_supported(
                conversation.provider,
                normalized_attachments,
            )
            llm = self._get_llm(conversation.provider, conversation.model_name)
            knowledge_context = await self._safe_retrieve_knowledge_context(
                user_message=user_message,
                user_id=user_id,
            )
            memory_context = await self._safe_retrieve_memory_context(
                user_message=user_message,
                user_id=user_id,
            )
            portfolio_context = await self._safe_retrieve_portfolio_context(
                user_id=user_id,
            )
            news_context = await self._safe_retrieve_news_context(
                user_id=user_id,
                user_message=user_message,
            )
            llm_messages = self._build_langchain_messages(
                history,
                user_message,
                normalized_attachments,
                provider=conversation.provider,
                knowledge_context=knowledge_context,
                memory_context=memory_context,
                portfolio_context=portfolio_context,
                news_context=news_context,
            )
            raw_stream = llm.astream(llm_messages).__aiter__()
            first_chunk = await anext(raw_stream, None)
        except ProviderRequestError:
            if lock.locked():
                lock.release()
            raise
        except InvalidProviderModelError:
            if lock.locked():
                lock.release()
            raise
        except ConversationNotFoundError:
            if lock.locked():
                lock.release()
            raise
        except Exception as exc:
            if lock.locked():
                lock.release()
            logger.exception(
                "Provider request failed before streaming started for conversation %s.",
                conversation_id,
            )
            raise ProviderRequestError() from exc

        async def iterator() -> AsyncIterator[str]:
            assistant_parts: list[str] = []

            try:
                if first_chunk is not None:
                    first_token = self._extract_text(
                        getattr(first_chunk, "content", first_chunk)
                    )
                    if first_token:
                        assistant_parts.append(first_token)
                        yield first_token

                async for chunk in raw_stream:
                    token = self._extract_text(getattr(chunk, "content", chunk))
                    if not token:
                        continue
                    assistant_parts.append(token)
                    yield token

                await self._persist_exchange(
                    conversation=conversation,
                    history=history,
                    user_message=user_message,
                    attachments=self._attachments_for_storage(normalized_attachments),
                    assistant_content="".join(assistant_parts),
                    token_count=None,
                )
                await self._maybe_store_conversation_memory(
                    conversation=conversation,
                    user_id=user_id,
                )
                yield "[DONE]"
            except Exception:
                logger.exception(
                    "Streaming response failed for conversation %s.",
                    conversation_id,
                )
                yield "[DONE]"
            finally:
                if lock.locked():
                    lock.release()

        return iterator()

    async def _get_conversation(self, user_id: str, conversation_id: uuid.UUID):
        conversation = await self.conversation_repo.get_by_id_for_user(
            conversation_id,
            user_id,
        )
        if conversation is None:
            raise ConversationNotFoundError()

        provider, model_name = self._resolve_provider_model(
            conversation.provider,
            conversation.model_name,
        )
        if conversation.provider != provider or conversation.model_name != model_name:
            conversation.provider = provider
            conversation.model_name = model_name
            await self.session.commit()
        return conversation

    async def _apply_requested_model(
        self,
        conversation: Conversation,
        *,
        provider: str | None,
        model_name: str | None,
    ) -> Conversation:
        next_provider = (provider or conversation.provider).strip()
        next_model_name = (model_name or conversation.model_name).strip()
        resolved_provider, resolved_model_name = self._resolve_provider_model(
            next_provider,
            next_model_name,
        )

        if (
            conversation.provider == resolved_provider
            and conversation.model_name == resolved_model_name
        ):
            return conversation

        conversation.provider = resolved_provider
        conversation.model_name = resolved_model_name
        await self.conversation_repo.touch(conversation)
        await self.session.commit()
        return conversation

    async def _load_history(self, conversation_id: uuid.UUID) -> list[dict[str, Any]]:
        cache_key = self._history_cache_key(conversation_id)
        cached = await self.cache_service.get(cache_key)
        if isinstance(cached, list):
            return cached[-self.history_limit :]

        messages = await self.message_repo.get_recent_for_conversation(
            conversation_id,
            limit=self.history_limit,
        )
        history = [self._serialize_message(message) for message in messages]
        if history:
            await self._write_history_cache(cache_key, history)
        return history

    def _get_llm(self, provider: str, model_name: str):
        try:
            return LLMFactory.get_llm(provider, model_name)
        except ValueError as exc:
            msg = f"Unsupported model '{model_name}' for provider '{provider}'."
            raise InvalidProviderModelError(msg) from exc

    async def _persist_exchange(
        self,
        *,
        conversation: Conversation,
        history: list[dict[str, Any]],
        user_message: str,
        attachments: list[dict[str, Any]],
        assistant_content: str,
        token_count: int | None,
    ) -> tuple[Message, list[dict[str, Any]]]:
        user_record = await self.message_repo.create(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=encode_user_message_content(user_message, attachments),
        )
        assistant_record = await self.message_repo.create(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=assistant_content,
            token_count=token_count,
        )
        await self.conversation_repo.touch(conversation)
        await self.session.commit()
        await self.session.refresh(user_record)
        await self.session.refresh(assistant_record)

        updated_history = [
            *history,
            self._serialize_message(user_record),
            self._serialize_message(assistant_record),
        ][-self.history_limit :]
        await self._write_history_cache(
            self._history_cache_key(conversation.id),
            updated_history,
        )
        return assistant_record, updated_history

    async def _write_history_cache(
        self,
        cache_key: str,
        history: list[dict[str, Any]],
    ) -> None:
        was_written = await self.cache_service.set(
            cache_key,
            history,
            self.cache_ttl_seconds,
        )
        if not was_written:
            await self.cache_service.delete(cache_key)

    def _build_langchain_messages(
        self,
        history: list[dict[str, Any]],
        user_message: str,
        attachments: list[dict[str, Any]],
        *,
        provider: str,
        knowledge_context: list[str],
        memory_context: list[str],
        portfolio_context: dict[str, Any] | None,
        news_context: dict[str, Any] | None,
    ) -> list[HumanMessage | AIMessage | SystemMessage]:
        messages: list[HumanMessage | AIMessage | SystemMessage] = [
            SystemMessage(content=SYSTEM_SCRATCHPAD_PROMPT)
        ]
        if portfolio_context:
            messages.append(
                SystemMessage(content=self._format_portfolio_context(portfolio_context))
            )
        if news_context:
            messages.append(
                SystemMessage(content=self._format_news_context(news_context))
            )
        if memory_context:
            messages.append(
                SystemMessage(content=self._format_memory_context(memory_context))
            )
        if knowledge_context:
            messages.append(
                SystemMessage(content=self._format_knowledge_context(knowledge_context))
            )

        for item in history:
            role = item["role"]
            content = item["content"]
            if role == MessageRole.USER.value:
                messages.append(
                    HumanMessage(
                        content=self._build_user_message_payload(
                            content,
                            item.get("attachments", []),
                            provider=provider,
                        )
                    )
                )
            elif role == MessageRole.ASSISTANT.value:
                messages.append(AIMessage(content=content))
            else:
                messages.append(SystemMessage(content=content))

        messages.append(
            HumanMessage(
                content=self._build_user_message_payload(
                    user_message,
                    attachments,
                    provider=provider,
                )
            )
        )
        return messages

    def _serialize_message(self, message: Message) -> dict[str, Any]:
        return serialize_message_for_history(message)

    @staticmethod
    def _normalize_attachments(
        attachments: list[ChatAttachmentRequest],
    ) -> list[dict[str, Any]]:
        return [attachment.model_dump(exclude_none=True) for attachment in attachments]

    @staticmethod
    def _attachments_for_storage(
        attachments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "kind": attachment["kind"],
                "name": attachment["name"],
                "mime_type": attachment["mime_type"],
            }
            for attachment in attachments
        ]

    def _build_user_message_payload(
        self,
        content: str,
        attachments: list[dict[str, Any]],
        *,
        provider: str,
    ) -> str | list[dict[str, Any]]:
        if not attachments:
            return content

        supports_image_inputs = self._supports_image_inputs(provider)
        blocks: list[dict[str, Any]] = []

        if content:
            blocks.append({"type": "text", "text": content})

        for attachment in attachments:
            if attachment["kind"] == "file":
                blocks.append(
                    {
                        "type": "text",
                        "text": self._format_file_attachment_text(attachment),
                    }
                )
                continue

            blocks.append(
                {
                    "type": "text",
                    "text": f"Attached image: {attachment['name']}",
                }
            )
            if supports_image_inputs and "data_url" in attachment:
                blocks.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": attachment["data_url"]},
                    }
                )

        return blocks

    @staticmethod
    def _format_file_attachment_text(attachment: dict[str, Any]) -> str:
        return (
            f"Attached file: {attachment['name']}\n"
            f"MIME type: {attachment['mime_type']}\n"
            f"{attachment.get('text_content', '')}"
        )

    @staticmethod
    def _supports_image_inputs(provider: str) -> bool:
        return provider in {"openai", "google"}

    def _ensure_image_attachments_supported(
        self,
        provider: str,
        attachments: list[dict[str, Any]],
    ) -> None:
        if self._supports_image_inputs(provider):
            return

        if any(attachment["kind"] == "image" for attachment in attachments):
            msg = (
                "The selected provider/model does not support image attachments. "
                "Choose GPT-4o or Gemini to send images."
            )
            raise InvalidProviderModelError(msg)

    async def _safe_retrieve_knowledge_context(
        self,
        *,
        user_message: str,
        user_id: str,
    ) -> list[str]:
        try:
            return await self.pinecone_service.retrieve_context(
                user_message=user_message,
                user_id=user_id,
                top_k=5,
            )
        except Exception:
            logger.exception("Knowledge retrieval failed for user %s.", user_id)
            return []

    async def _safe_retrieve_memory_context(
        self,
        *,
        user_message: str,
        user_id: str,
    ) -> list[str]:
        try:
            return await self.pinecone_service.retrieve_memories(
                user_id=user_id,
                user_message=user_message,
                top_k=3,
            )
        except Exception:
            logger.exception("Memory retrieval failed for user %s.", user_id)
            return []

    async def _safe_retrieve_portfolio_context(
        self,
        *,
        user_id: str,
    ) -> dict[str, Any] | None:
        combined_context: dict[str, Any] = {}
        try:
            angel_context = await self.portfolio_sync_service.get_portfolio_snapshot(
                user_id=user_id,
                trigger="agent_request",
                force_refresh=False,
            )
            if angel_context:
                combined_context["angel_one"] = angel_context
        except Exception:
            logger.debug("No Angel One portfolio available for user %s.", user_id)

        try:
            if self.groww_broker_service is not None:
                groww_context = await self.groww_broker_service.get_portfolio(
                    user_id=user_id,
                    trigger="agent_request",
                    force_refresh=False,
                )
                if groww_context:
                    combined_context["groww"] = groww_context
        except Exception:
            logger.debug("No Groww portfolio available for user %s.", user_id)

        return combined_context if combined_context else None

    async def _safe_retrieve_news_context(
        self,
        *,
        user_id: str,
        user_message: str,
    ) -> dict[str, Any] | None:
        if not self._should_use_news_context(user_message):
            return None

        connection_service = MCPConnectionService(
            cache_service=self.cache_service,
            settings=self.settings,
            connection_ttl_seconds=self.settings.mcp_connection_ttl_seconds,
        )
        try:
            if not await connection_service.is_connected(
                user_id=user_id,
                provider="newsapi",
            ):
                return None
            tool_name = self._select_news_tool(user_message)
            if tool_name not in ALLOWED_NEWSAPI_TOOLS:
                return None
            result = await connection_service.call_tool(
                user_id=user_id,
                provider="newsapi",
                tool_name=tool_name,
                arguments=self._build_news_arguments(
                    tool_name=tool_name,
                    user_message=user_message,
                    max_results=6,
                ),
            )
            return {"tool": tool_name, "result": result}
        except Exception:
            logger.exception("NewsAPI MCP retrieval failed for user %s.", user_id)
            return None

    @staticmethod
    def _should_use_news_context(user_message: str) -> bool:
        normalized = user_message.lower()
        keywords = (
            "buy",
            "sell",
            "stock",
            "share",
            "market",
            "news",
            "latest",
            "current",
            "today",
            "event",
            "happened",
            "funding",
            "regulation",
            "reliance",
            "relience",
        )
        return any(keyword in normalized for keyword in keywords)

    @staticmethod
    def _select_news_tool(user_message: str) -> str:
        normalized = user_message.lower()
        if any(
            keyword in normalized
            for keyword in ("event", "events", "happened", "conference")
        ):
            return "search_events"
        return "search_articles"

    @staticmethod
    def _build_news_arguments(
        *,
        tool_name: str,
        user_message: str,
        max_results: int,
    ) -> dict[str, Any]:
        if tool_name == "search_events":
            return {
                "keyword": user_message,
                "lang": "eng",
                "eventsCount": max_results,
                "eventsSortBy": "date",
            }
        return {
            "keyword": user_message,
            "lang": "eng",
            "articlesCount": max_results,
            "articlesSortBy": "date",
        }

    async def _maybe_store_conversation_memory(
        self,
        *,
        conversation: Conversation,
        user_id: str,
    ) -> None:
        if not self.pinecone_service.enabled:
            return

        messages = await self.message_repo.list_for_conversation(conversation.id)
        if not messages or len(messages) % self.memory_summary_window != 0:
            return

        segment = messages[-self.memory_summary_window :]
        transcript = [self._serialize_message(message) for message in segment]
        summary = await self._summarize_memory_segment(
            transcript,
            provider=conversation.provider,
            model_name=conversation.model_name,
        )
        if not summary:
            return

        try:
            await self.pinecone_service.store_memory_summary(
                user_id=user_id,
                conversation_id=str(conversation.id),
                summary=summary,
                segment_key=str(len(messages) // self.memory_summary_window),
            )
        except Exception:
            logger.exception(
                "Persisting conversation memory failed for conversation %s.",
                conversation.id,
            )

    async def _summarize_memory_segment(
        self,
        messages: list[dict[str, Any]],
        *,
        provider: str,
        model_name: str,
    ) -> str:
        transcript_lines = [
            f"{item.get('role', 'unknown')}: {str(item.get('content', '')).strip()}"
            for item in messages
            if str(item.get("content", "")).strip()
        ]
        if not transcript_lines:
            return ""

        try:
            try:
                llm = self._get_llm(MEMORY_SUMMARY_PROVIDER, MEMORY_SUMMARY_MODEL)
            except InvalidProviderModelError:
                llm = self._get_llm(provider, model_name)
            response = await llm.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "Summarize this conversation segment in 3-5 sentences, "
                            "capturing key facts, decisions, and user preferences."
                        )
                    ),
                    HumanMessage(content="\n".join(transcript_lines)),
                ]
            )
        except Exception:
            logger.exception("Conversation memory summarization failed.")
            return ""

        return self._extract_text(getattr(response, "content", response)).strip()

    @staticmethod
    def _format_knowledge_context(context_blocks: list[str]) -> str:
        return (
            "KNOWLEDGE BASE CONTEXT (from user's uploaded assets):\n"
            "---\n" + "\n".join(context_blocks) + "\n---\n"
            "Use this context to answer the user's question when relevant. "
            "If the context is not relevant, answer from your general knowledge."
        )

    @staticmethod
    def _format_memory_context(memory_context: list[str]) -> str:
        return "CONVERSATION MEMORY:\n" + "\n".join(
            f"- {summary}" for summary in memory_context
        )

    @staticmethod
    def _format_portfolio_context(portfolio_context: dict[str, Any]) -> str:
        if not portfolio_context:
            return "No active broker portfolios connected."

        formatted_parts = []
        for broker_key, broker_data in portfolio_context.items():
            broker_raw = broker_data.get("broker", broker_key)
            broker_label = {
                "angel_one": "Angel One",
                "groww": "Groww",
            }.get(
                broker_raw,
                broker_raw.replace("_", " ").title() if broker_raw else "your broker",
            )

            summary_json = json.dumps(
                broker_data.get("summary", {}),
                separators=(",", ":"),
            )
            holdings_json = json.dumps(
                broker_data.get("holdings", []),
                separators=(",", ":"),
            )
            positions_json = json.dumps(
                broker_data.get("positions", []),
                separators=(",", ":"),
            )
            funds_json = json.dumps(
                broker_data.get("funds", {}),
                separators=(",", ":"),
            )
            order_history_json = json.dumps(
                broker_data.get("order_history", [])[:5],
                separators=(",", ":"),
            )

            formatted_parts.append(
                f"--- {broker_label} Portfolio Snapshot ---\n"
                f"Summary: {summary_json}\n"
                f"Holdings: {holdings_json}\n"
                f"Positions: {positions_json}\n"
                f"Funds available: {funds_json}\n"
                f"Recent orders: {order_history_json}\n"
            )

        return (
            "The user has connected the following broker portfolios. Use this "
            "data to answer portfolio-related questions accurately.\n"
            "Data is cached and may be up to 60 seconds old.\n\n"
            + "\n".join(formatted_parts)
        )

    @staticmethod
    def _format_news_context(news_context: dict[str, Any]) -> str:
        compact_result = json.dumps(
            news_context.get("result", {}),
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        )[:16_000]
        return (
            "NEWSAPI MCP CONTEXT:\n"
            f"Tool used: {news_context.get('tool', 'search_articles')}\n"
            f"Result JSON: {compact_result}\n\n"
            "Use this current news context only when relevant. Do not invent "
            "facts. For investing questions, combine portfolio context and news "
            "carefully, explain risk, and avoid guaranteeing returns."
        )

    def _extract_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        return str(value) if value is not None else ""

    def _extract_token_count(self, response: Any) -> int | None:
        usage = getattr(response, "usage_metadata", None)
        if isinstance(usage, dict):
            total_tokens = usage.get("total_tokens")
            if isinstance(total_tokens, int):
                return total_tokens

        response_metadata = getattr(response, "response_metadata", None)
        if isinstance(response_metadata, dict):
            token_usage = response_metadata.get("token_usage") or response_metadata.get(
                "usage"
            )
            if isinstance(token_usage, dict):
                total_tokens = token_usage.get("total_tokens")
                if isinstance(total_tokens, int):
                    return total_tokens
        return None

    @classmethod
    def _get_lock(cls, conversation_id: uuid.UUID) -> asyncio.Lock:
        lock = cls._conversation_locks.get(conversation_id)
        if lock is None:
            lock = asyncio.Lock()
            cls._conversation_locks[conversation_id] = lock
        return lock

    @classmethod
    def _conversation_lock(cls, conversation_id: uuid.UUID) -> asyncio.Lock:
        return cls._get_lock(conversation_id)

    @staticmethod
    def _history_cache_key(conversation_id: uuid.UUID) -> str:
        return chat_history_key(conversation_id=str(conversation_id))

    @staticmethod
    def _resolve_provider_model(provider: str, model_name: str) -> tuple[str, str]:
        try:
            return LLMRouter.resolve_provider_model(provider, model_name)
        except ValueError as exc:
            msg = f"Unsupported model '{model_name}' for provider '{provider}'."
            raise InvalidProviderModelError(msg) from exc
