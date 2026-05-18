"""Helpers for server-sent event streaming responses."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable


def format_sse_event(payload: str) -> str:
    """Format a text payload as a server-sent event line."""
    lines = payload.split("\n")
    return "".join(f"data: {line}\n" for line in lines) + "\n"


async def iter_sse_events(
    payload_iterator: AsyncIterator[str],
    *,
    is_disconnected: Callable[[], Awaitable[bool]] | None = None,
    keepalive_seconds: float = 15.0,
) -> AsyncIterator[str]:
    """Wrap payload iteration in SSE formatting with keepalive and disconnect checks."""
    while True:
        if is_disconnected is not None and await is_disconnected():
            return

        try:
            payload = await asyncio.wait_for(
                payload_iterator.__anext__(),
                timeout=keepalive_seconds,
            )
        except TimeoutError:
            # Comment line heartbeat keeps proxies/browsers from buffering indefinitely.
            yield ": keep-alive\n\n"
            continue
        except StopAsyncIteration:
            return

        yield format_sse_event(payload)
