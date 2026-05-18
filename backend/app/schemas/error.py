"""Error response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    """Structured API error details."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class ErrorResponse(BaseModel):
    """API error response envelope."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail
