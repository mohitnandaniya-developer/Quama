"""Model catalog endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.llm_router import LLMRouter
from app.schemas.model_info import ModelsResponse, ProviderInfo

router = APIRouter()


@router.get("", response_model=ModelsResponse)
async def get_models() -> ModelsResponse:
    """Return the list of supported providers and models."""
    providers = [ProviderInfo.model_validate(item) for item in LLMRouter.get_catalog()]
    return ModelsResponse(providers=providers)
