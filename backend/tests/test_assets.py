"""Permanent asset endpoint tests."""

from __future__ import annotations

import pytest

PNG_DATA_URL = "data:image/png;base64,aW1hZ2U="


@pytest.mark.asyncio
async def test_upload_list_and_delete_assets(
    client,
    user_headers,
) -> None:
    """Permanent assets are exposed through the API."""
    upload_response = await client.post(
        "/api/v1/assets",
        headers=user_headers,
        json={
            "attachments": [
                {
                    "kind": "file",
                    "name": "notes.md",
                    "mime_type": "text/markdown",
                    "text_content": "# Stored asset",
                },
                {
                    "kind": "image",
                    "name": "preview.png",
                    "mime_type": "image/png",
                    "data_url": PNG_DATA_URL,
                },
            ]
        },
    )

    assert upload_response.status_code == 201
    upload_payload = upload_response.json()
    assert len(upload_payload["items"]) == 2

    list_response = await client.get("/api/v1/assets", headers=user_headers)
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload["items"]) == 2

    delete_response = await client.delete(
        f"/api/v1/assets/{list_payload['items'][0]['id']}",
        headers=user_headers,
    )
    assert delete_response.status_code == 204

    refreshed_response = await client.get("/api/v1/assets", headers=user_headers)
    refreshed_payload = refreshed_response.json()
    assert len(refreshed_payload["items"]) == 1
