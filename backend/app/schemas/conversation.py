"""Conversation and message schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app.models.message import MessageRole
from app.schemas.chat import MessageAttachmentSchema

ProviderName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50),
]
ModelName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
ConversationTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class MessageSchema(BaseModel):
    """Serialized conversation message."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    role: MessageRole
    content: str
    attachments: list[MessageAttachmentSchema] = []
    token_count: int | None = None
    created_at: datetime


class ConversationCreate(BaseModel):
    """Conversation creation payload."""

    model_config = ConfigDict(extra="forbid")

    provider: ProviderName | None = None
    model_name: ModelName | None = None
    title: ConversationTitle | None = Field(default=None)

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ConversationSchema(BaseModel):
    """Serialized conversation metadata."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    user_id: str
    title: str
    provider: str
    model_name: str
    created_at: datetime
    updated_at: datetime


class ConversationDetailResponse(BaseModel):
    """Conversation detail response including messages."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    conversation: ConversationSchema
    messages: list[MessageSchema]


class ConversationListResponse(BaseModel):
    """Paginated conversation list response."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    items: list[ConversationSchema]
    total: int
    skip: int
    limit: int
