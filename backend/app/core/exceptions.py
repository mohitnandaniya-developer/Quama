"""Application-level domain exceptions."""

from __future__ import annotations


class AppError(Exception):
    """Base class for domain exceptions returned through the API layer."""

    status_code = 500
    code = "internal_server_error"
    default_message = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class MissingUserIdError(AppError):
    """Raised when a required user header is missing."""

    status_code = 422
    code = "missing_user_id"
    default_message = "X-User-Id header is required."


class AuthenticationError(AppError):
    """Raised when a request is missing or has invalid authentication."""

    status_code = 401
    code = "authentication_failed"
    default_message = "Authentication is required."


class ConversationNotFoundError(AppError):
    """Raised when a conversation cannot be resolved for a user."""

    status_code = 404
    code = "conversation_not_found"
    default_message = "Conversation not found."


class InvalidProviderModelError(AppError):
    """Raised when a provider/model pair is not in the catalog."""

    status_code = 422
    code = "invalid_provider_model"
    default_message = "The selected provider/model is not supported."


class ProviderRequestError(AppError):
    """Raised when an upstream LLM provider call fails."""

    status_code = 502
    code = "provider_request_failed"
    default_message = "The model provider request failed."


class BrokerNotConfiguredError(AppError):
    """Raised when broker settings are incomplete."""

    status_code = 503
    code = "broker_not_configured"
    default_message = "Broker integration is not configured."


class BrokerAuthError(AppError):
    """Raised when broker credentials are invalid."""

    status_code = 400
    code = "broker_auth_failed"
    default_message = "Invalid credentials."


class BrokerTotpError(AppError):
    """Raised when broker TOTP is invalid."""

    status_code = 400
    code = "broker_totp_failed"
    default_message = "Wrong TOTP."


class BrokerSessionNotFoundError(AppError):
    """Raised when no active broker session exists for a user."""

    status_code = 404
    code = "broker_session_not_found"
    default_message = "Broker session not found. Please reconnect your broker."


class BrokerRefreshError(AppError):
    """Raised when broker token refresh fails."""

    status_code = 502
    code = "broker_refresh_failed"
    default_message = "Broker token refresh failed."


class InvalidBrokerError(AppError):
    """Raised when a request references an unsupported broker id."""

    status_code = 422
    code = "invalid_broker"
    default_message = "The selected broker is not supported."


class PortfolioSyncError(AppError):
    """Raised when portfolio synchronization fails."""

    status_code = 502
    code = "portfolio_sync_failed"
    default_message = "Portfolio synchronization failed."


class MarketDataNotConfiguredError(AppError):
    """Raised when direct Redis market streaming infrastructure is unavailable."""

    status_code = 503
    code = "market_data_not_configured"
    default_message = "Market data infrastructure is not configured."


class MCPConnectionError(AppError):
    """Raised when an MCP connection cannot be established or used."""

    status_code = 400
    code = "mcp_connection_failed"
    default_message = "MCP connection failed."


class MCPToolNotFoundError(AppError):
    """Raised when an MCP tool cannot be found for a user."""

    status_code = 404
    code = "mcp_tool_not_found"
    default_message = "MCP tool not found."
