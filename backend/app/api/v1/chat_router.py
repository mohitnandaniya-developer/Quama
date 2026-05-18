"""Chat endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from app.core.streaming import iter_sse_events
from app.dependencies import get_chat_service, require_user_id
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse
from app.services.chat_service import ChatService

router = APIRouter()


@router.post(
    "/message",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    payload: ChatMessageRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatMessageResponse:
    """Send a chat message and return the assistant response."""
    return await service.send_message(
        user_id=user_id,
        conversation_id=payload.conversation_id,
        user_message=payload.content,
        provider=payload.provider,
        model_name=payload.model_name,
        attachments=payload.attachments,
    )


@router.post("/stream", response_class=StreamingResponse)
async def stream_message(
    payload: ChatMessageRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> StreamingResponse:
    """Stream a chat response as server-sent events."""
    payload_iterator = await service.stream_message(
        user_id=user_id,
        conversation_id=payload.conversation_id,
        user_message=payload.content,
        provider=payload.provider,
        model_name=payload.model_name,
        attachments=payload.attachments,
    )

    return StreamingResponse(
        iter_sse_events(payload_iterator),
        media_type="text/event-stream",
    )
