"""Permanent asset request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

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
    StringConstraints(min_length=1, max_length=200_000),
]
AttachmentDataUrl = Annotated[
    str,
    StringConstraints(min_length=1, max_length=15_000_000),
]


class AssetUploadAttachmentRequest(BaseModel):
    """Attachment payload used for permanent asset uploads."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["file", "image"]
    name: AttachmentName
    mime_type: AttachmentMimeType
    text_content: AttachmentTextContent | None = None
    data_url: AttachmentDataUrl | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> AssetUploadAttachmentRequest:
        if self.data_url is None and self.text_content is None:
            raise ValueError("data_url or text_content is required for assets.")
        if self.kind == "image" and not self.mime_type.startswith("image/"):
            raise ValueError("image assets must use an image mime_type.")
        return self


class AssetUploadRequest(BaseModel):
    """Request body for permanent asset uploads."""

    model_config = ConfigDict(extra="forbid")

    attachments: list[AssetUploadAttachmentRequest]

    @model_validator(mode="after")
    def validate_payload(self) -> AssetUploadRequest:
        if not self.attachments:
            raise ValueError("attachments must include at least one file or image.")
        return self


class AssetSchema(BaseModel):
    """Serialized stored asset metadata."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    kind: str
    mime_type: str
    size_bytes: int
    pinecone_indexed: bool
    created_at: datetime
    updated_at: datetime


class AssetListResponse(BaseModel):
    """Paginated-like stored asset list."""

    model_config = ConfigDict(extra="forbid")

    items: list[AssetSchema]


class AssetUploadResponse(BaseModel):
    """Upload response payload."""

    model_config = ConfigDict(extra="forbid")

    items: list[AssetSchema]
