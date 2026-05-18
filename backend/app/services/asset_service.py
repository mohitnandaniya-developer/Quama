"""Asset metadata service."""

from __future__ import annotations

import base64
import logging
import re
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.repositories.user_asset_repo import UserAssetRepository
from app.models.user_asset import UserAsset, UserAssetKind
from app.schemas.asset import (
    AssetListResponse,
    AssetSchema,
    AssetUploadAttachmentRequest,
    AssetUploadResponse,
)

logger = logging.getLogger(__name__)


class AssetNotFoundError(AppError):
    """Raised when a stored asset cannot be resolved for a user."""

    status_code = 404
    code = "asset_not_found"
    default_message = "Asset not found."


class AssetService:
    """Persist uploaded asset metadata."""

    def __init__(
        self,
        *,
        session: AsyncSession,
    ) -> None:
        self.session = session
        self.asset_repo = UserAssetRepository(session)

    async def list_assets(self, *, user_id: str) -> AssetListResponse:
        """Return stored assets for the current user."""
        items = await self.asset_repo.list_for_user(user_id)
        return AssetListResponse(items=[self._serialize_asset(item) for item in items])

    async def upload_assets(
        self,
        *,
        user_id: str,
        attachments: list[AssetUploadAttachmentRequest],
    ) -> AssetUploadResponse:
        """Store uploaded asset metadata in the database."""
        stored_assets: list[UserAsset] = []
        for attachment in attachments:
            raw_bytes = self._attachment_bytes(attachment)
            suffix = Path(attachment.name).suffix or self._default_suffix(attachment)
            storage_name = (
                f"{uuid.uuid4().hex}-"
                f"{self._sanitize_file_stem(attachment.name)}{suffix}"
            )
            stored_assets.append(
                await self.asset_repo.create(
                    user_id=user_id,
                    name=Path(attachment.name).name,
                    kind=(
                        UserAssetKind.IMAGE
                        if attachment.kind == "image"
                        else UserAssetKind.FILE
                    ),
                    mime_type=attachment.mime_type,
                    size_bytes=len(raw_bytes),
                    storage_path=storage_name,
                )
            )

        await self.session.commit()
        for asset in stored_assets:
            await self.session.refresh(asset)
        return AssetUploadResponse(
            items=[self._serialize_asset(item) for item in stored_assets]
        )

    async def delete_asset(self, *, user_id: str, asset_id: uuid.UUID) -> None:
        """Delete a stored asset record."""
        asset = await self.asset_repo.get_by_id_for_user(asset_id, user_id)
        if asset is None:
            raise AssetNotFoundError()

        await self.asset_repo.delete(asset)
        await self.session.commit()

    def _serialize_asset(self, asset: UserAsset) -> AssetSchema:
        return AssetSchema(
            id=asset.id,
            name=asset.name,
            kind=asset.kind.value,
            mime_type=asset.mime_type,
            size_bytes=asset.size_bytes,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
        )

    @staticmethod
    def _attachment_bytes(attachment: AssetUploadAttachmentRequest) -> bytes:
        if attachment.data_url is not None:
            _, _, payload = attachment.data_url.partition(",")
            try:
                return base64.b64decode(payload)
            except ValueError as exc:
                raise ValueError("The asset payload is not valid base64 data.") from exc

        if attachment.text_content is not None:
            return attachment.text_content.encode("utf-8")

        raise ValueError("The asset payload is empty.")

    @staticmethod
    def _sanitize_file_stem(file_name: str) -> str:
        stem = Path(file_name).stem or "asset"
        normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", stem.strip())
        return normalized.strip("-.") or "asset"

    @staticmethod
    def _default_suffix(attachment: AssetUploadAttachmentRequest) -> str:
        return ".png" if attachment.kind == "image" else ".txt"
