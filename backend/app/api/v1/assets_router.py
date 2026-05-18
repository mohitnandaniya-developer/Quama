"""Permanent asset endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.dependencies import get_asset_service, require_user_id
from app.schemas.asset import AssetListResponse, AssetUploadRequest, AssetUploadResponse
from app.services.asset_service import AssetService

router = APIRouter()


@router.get("", response_model=AssetListResponse)
async def list_assets(
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[AssetService, Depends(get_asset_service)],
) -> AssetListResponse:
    """List permanently stored assets for the current user."""
    return await service.list_assets(user_id=user_id)


@router.post(
    "",
    response_model=AssetUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_assets(
    payload: AssetUploadRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[AssetService, Depends(get_asset_service)],
) -> AssetUploadResponse:
    """Store uploaded assets in the media library."""
    return await service.upload_assets(
        user_id=user_id,
        attachments=payload.attachments,
    )


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: uuid.UUID,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[AssetService, Depends(get_asset_service)],
) -> Response:
    """Delete a stored asset."""
    await service.delete_asset(user_id=user_id, asset_id=asset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
