"""User asset repository implementation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_asset import UserAsset, UserAssetKind


class UserAssetRepository:
    """Encapsulate permanent asset persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: str,
        name: str,
        kind: UserAssetKind,
        mime_type: str,
        size_bytes: int,
        storage_path: str,
        pinecone_indexed: bool = False,
    ) -> UserAsset:
        """Create and flush a new stored asset."""
        asset = UserAsset(
            user_id=user_id,
            name=name,
            kind=kind,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
            pinecone_indexed=pinecone_indexed,
        )
        self.session.add(asset)
        await self.session.flush()
        return asset

    async def list_for_user(self, user_id: str) -> list[UserAsset]:
        """Return assets for a user ordered from newest to oldest."""
        stmt = (
            select(UserAsset)
            .where(UserAsset.user_id == user_id)
            .order_by(UserAsset.created_at.desc(), UserAsset.id.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_id_for_user(
        self,
        asset_id: uuid.UUID,
        user_id: str,
    ) -> UserAsset | None:
        """Return a stored asset owned by the user."""
        stmt = select(UserAsset).where(
            UserAsset.id == asset_id,
            UserAsset.user_id == user_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def delete(self, asset: UserAsset) -> None:
        """Delete an asset record."""
        await self.session.delete(asset)

    async def touch(self, asset: UserAsset) -> UserAsset:
        """Update the asset timestamp."""
        asset.updated_at = datetime.now(UTC)
        await self.session.flush()
        return asset

    async def set_pinecone_indexed(
        self,
        asset: UserAsset,
        *,
        pinecone_indexed: bool,
    ) -> UserAsset:
        """Update the vector-index status for an asset."""
        asset.pinecone_indexed = pinecone_indexed
        asset.updated_at = datetime.now(UTC)
        await self.session.flush()
        return asset
