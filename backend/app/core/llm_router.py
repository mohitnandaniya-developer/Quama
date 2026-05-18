"""Provider and model catalog definitions."""

from __future__ import annotations

from copy import deepcopy

SUPPORTED_PROVIDERS: dict[str, dict[str, object]] = {
    "openai": {
        "models": [
            {
                "id": "gpt-4o",
                "name": "GPT-4o",
                "description": "OpenAI flagship multimodal chat model.",
            },
            {
                "id": "gpt-4o-mini",
                "name": "GPT-4o Mini",
                "description": "Lower-cost OpenAI model for fast chat responses.",
            },
            {
                "id": "gpt-3.5-turbo",
                "name": "GPT-3.5 Turbo",
                "description": "Legacy OpenAI chat model for lightweight workloads.",
            },
        ]
    },
    "google": {
        "models": [
            {
                "id": "gemini-1.5-pro",
                "name": "Gemini 1.5 Pro",
                "description": "Google's higher-capability Gemini model.",
            },
            {
                "id": "gemini-1.5-flash",
                "name": "Gemini 1.5 Flash",
                "description": "Fast Google Gemini model for lower-latency chat.",
            },
        ]
    },
    "groq": {
        "models": [
            {
                "id": "llama-3.3-70b-versatile",
                "name": "Llama 3.3 70B Versatile",
                "description": "Groq production model optimized for high-quality chat.",
            },
            {
                "id": "llama-3.1-8b-instant",
                "name": "Llama 3.1 8B Instant",
                "description": (
                    "Groq production model for fast, low-latency chat responses."
                ),
            },
            {
                "id": "openai/gpt-oss-120b",
                "name": "GPT OSS 120B",
                "description": "Groq-hosted OpenAI open-weight reasoning model.",
            },
            {
                "id": "openai/gpt-oss-20b",
                "name": "GPT OSS 20B",
                "description": "Groq-hosted compact OpenAI open-weight model.",
            },
        ]
    },
}

MODEL_ALIASES: dict[str, dict[str, str]] = {
    "groq": {
        "llama-3.1-70b-versatile": "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768": "llama-3.3-70b-versatile",
    }
}


class LLMRouter:
    """Expose supported provider/model metadata and validation."""

    @classmethod
    def get_catalog(cls) -> list[dict[str, object]]:
        """Return the provider catalog in API-ready form."""
        return [
            {
                "name": provider,
                "models": deepcopy(provider_data["models"]),
            }
            for provider, provider_data in SUPPORTED_PROVIDERS.items()
        ]

    @classmethod
    def validate_provider_model(cls, provider: str, model_name: str) -> None:
        """Validate a provider/model combination."""
        cls.resolve_provider_model(provider, model_name)

    @classmethod
    def resolve_provider_model(
        cls,
        provider: str,
        model_name: str,
    ) -> tuple[str, str]:
        """Resolve deprecated aliases and validate the provider/model pair."""
        provider_data = SUPPORTED_PROVIDERS.get(provider)
        if provider_data is None:
            msg = f"Unsupported provider: {provider}"
            raise ValueError(msg)

        resolved_model_name = MODEL_ALIASES.get(provider, {}).get(
            model_name,
            model_name,
        )
        valid_model_ids = {model["id"] for model in provider_data["models"]}  # type: ignore[index]
        if resolved_model_name not in valid_model_ids:
            msg = f"Unsupported model '{model_name}' for provider '{provider}'."
            raise ValueError(msg)
        return provider, resolved_model_name
