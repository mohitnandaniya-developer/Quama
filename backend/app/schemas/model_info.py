"""Model catalog schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelInfo(BaseModel):
    """Metadata for a single model option."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    name: str
    description: str


class ProviderInfo(BaseModel):
    """Metadata for a single provider and its models."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    name: str
    models: list[ModelInfo]


class ModelsResponse(BaseModel):
    """Model catalog response."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    providers: list[ProviderInfo]
