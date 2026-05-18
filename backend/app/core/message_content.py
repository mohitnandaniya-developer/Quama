"""Helpers for encoding and decoding structured user message content."""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

from app.models.message import Message, MessageRole

USER_MESSAGE_SCHEMA = "quama.user-message.v1"


def encode_user_message_content(
    content: str,
    attachments: list[dict[str, Any]],
) -> str:
    """Persist user content as plain text or a structured attachment envelope."""
    if not attachments:
        return content

    return json.dumps(
        {
            "schema": USER_MESSAGE_SCHEMA,
            "content": content,
            "attachments": attachments,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def decode_user_message_content(
    role: MessageRole | str,
    raw_content: str,
) -> dict[str, Any]:
    """Return normalized text and attachments from stored message content."""
    normalized_role = role.value if isinstance(role, MessageRole) else role
    if normalized_role != MessageRole.USER.value:
        return {"content": raw_content, "attachments": []}

    try:
        payload = json.loads(raw_content)
    except JSONDecodeError:
        return {"content": raw_content, "attachments": []}

    if not isinstance(payload, dict) or payload.get("schema") != USER_MESSAGE_SCHEMA:
        return {"content": raw_content, "attachments": []}

    content = payload.get("content")
    attachments = payload.get("attachments")
    if not isinstance(content, str) or not isinstance(attachments, list):
        return {"content": raw_content, "attachments": []}

    normalized_attachments: list[dict[str, Any]] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue

        kind = attachment.get("kind")
        name = attachment.get("name")
        mime_type = attachment.get("mime_type")
        if (
            kind not in {"file", "image"}
            or not isinstance(name, str)
            or not isinstance(mime_type, str)
        ):
            continue

        normalized_attachment: dict[str, Any] = {
            "kind": kind,
            "name": name,
            "mime_type": mime_type,
        }

        if kind == "file":
            text_content = attachment.get("text_content")
            if isinstance(text_content, str):
                normalized_attachment["text_content"] = text_content
        else:
            data_url = attachment.get("data_url")
            if isinstance(data_url, str):
                normalized_attachment["data_url"] = data_url

        normalized_attachments.append(normalized_attachment)

    return {
        "content": content,
        "attachments": normalized_attachments,
    }


def serialize_message_for_api(message: Message) -> dict[str, Any]:
    """Shape a stored message for API responses."""
    payload = decode_user_message_content(message.role, message.content)
    attachments = [
        {
            "kind": attachment["kind"],
            "name": attachment["name"],
            "mime_type": attachment["mime_type"],
        }
        for attachment in payload["attachments"]
    ]

    return {
        "id": message.id,
        "role": message.role,
        "content": payload["content"],
        "attachments": attachments,
        "token_count": message.token_count,
        "created_at": message.created_at,
    }


def serialize_message_for_history(message: Message) -> dict[str, Any]:
    """Shape a stored message for cached history reconstruction."""
    payload = decode_user_message_content(message.role, message.content)
    return {
        "id": str(message.id),
        "role": message.role.value,
        "content": payload["content"],
        "attachments": payload["attachments"],
        "token_count": message.token_count,
        "created_at": message.created_at.isoformat(),
    }
