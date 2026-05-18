"""Chat request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

ChatContent = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=10000),
]
AttachmentName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
AttachmentMimeType = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
AttachmentTextContent = Annotated[
    str,
    StringConstraints(min_length=1, max_length=20000),
]
AttachmentDataUrl = Annotated[
    str,
    StringConstraints(min_length=1, max_length=6_000_000),
]


class ChatAttachmentRequest(BaseModel):
    """Serialized attachment payload included with a chat message."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["file", "image"]
    name: AttachmentName
    mime_type: AttachmentMimeType
    text_content: AttachmentTextContent | None = None
    data_url: AttachmentDataUrl | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> ChatAttachmentRequest:
        if self.kind == "file":
            if self.text_content is None and self.data_url is None:
                raise ValueError(
                    "text_content or data_url is required for file attachments."
                )
        if self.kind == "image":
            if self.data_url is None:
                raise ValueError("data_url is required for image attachments.")
            if not self.mime_type.startswith("image/"):
                raise ValueError("image attachments must use an image mime_type.")
        return self


class MessageAttachmentSchema(BaseModel):
    """Attachment metadata returned with stored conversation messages."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["file", "image"]
    name: AttachmentName
    mime_type: AttachmentMimeType


class ChatMessageRequest(BaseModel):
    """Request body for sending a chat message."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: uuid.UUID
    content: ChatContent
    provider: str | None = None
    model_name: str | None = None
    attachments: list[ChatAttachmentRequest] = []

    @model_validator(mode="after")
    def validate_payload(self) -> ChatMessageRequest:
        if not self.content and not self.attachments:
            raise ValueError("content or attachments must be provided.")
        return self


class ChatMessageResponse(BaseModel):
    """Assistant chat response payload."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    message_id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    token_count: int | None = None
