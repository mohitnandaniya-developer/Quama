"""Conversation endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.message_content import serialize_message_for_api
from app.dependencies import get_conversation_service, require_user_id
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationSchema,
    MessageSchema,
)
from app.services.conversation_service import ConversationService

router = APIRouter()


@router.post(
    "",
    response_model=ConversationSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ConversationCreate,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationSchema:
    """Create a new conversation."""
    conversation = await service.create_conversation(
        user_id=user_id,
        payload=payload,
    )
    return ConversationSchema.model_validate(conversation)


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> ConversationListResponse:
    """Return paginated conversations for the current user."""
    items, total = await service.list_conversations(
        user_id=user_id,
        skip=skip,
        limit=limit,
    )
    return ConversationListResponse(
        items=[ConversationSchema.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationDetailResponse:
    """Return a conversation and its messages."""
    conversation, messages = await service.get_conversation_detail(
        user_id=user_id,
        conversation_id=conversation_id,
    )
    return ConversationDetailResponse(
        conversation=ConversationSchema.model_validate(conversation),
        messages=[
            MessageSchema.model_validate(serialize_message_for_api(message))
            for message in messages
        ],
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> Response:
    """Soft-delete a conversation."""
    await service.delete_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
