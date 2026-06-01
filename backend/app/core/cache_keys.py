"""Canonical Redis key helpers for cache and pub/sub data."""


def chat_history_key(*, conversation_id: str) -> str:
    """Return the recent chat history cache key for one conversation."""
    return f"chat:history:{conversation_id}"


def broker_jwt_key(*, user_id: str, broker: str) -> str:
    """Return the JWT cache key for a broker session."""
    return f"broker:{broker}:{user_id}:jwt"


def portfolio_snapshot_key(*, user_id: str) -> str:
    """Return the cached portfolio snapshot key."""
    return f"portfolio:{user_id}"


def market_channel(*, instrument_token: str) -> str:
    """Return the live tick pub/sub channel for one instrument."""
    return f"market:{instrument_token}"


def market_snapshot_key(*, instrument_token: str) -> str:
    """Return the latest market snapshot cache key for one instrument."""
    return f"market:snapshot:{instrument_token}"


def market_subscription_key(*, user_id: str) -> str:
    """Return one desired-subscription registry key."""
    return f"market:subscriptions:{user_id}"


def market_subscription_pattern() -> str:
    """Return the scan pattern for subscription registries."""
    return "market:subscriptions:*"


def market_command_channel() -> str:
    """Return the control-plane pub/sub channel for the market worker."""
    return "market:commands"


def mcp_connection_key(*, user_id: str, provider: str) -> str:
    """Return one user MCP connection cache key."""
    return f"mcp:connection:{user_id}:{provider}"


def mcp_connections_index_key(*, user_id: str) -> str:
    """Return the user MCP provider index cache key."""
    return f"mcp:connections:{user_id}"
