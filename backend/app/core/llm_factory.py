"""Factory for LangChain chat model clients."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.core.llm_router import LLMRouter


class LLMFactory:
    """Create provider-specific LangChain chat model instances."""

    @staticmethod
    def get_llm(provider: str, model_name: str) -> BaseChatModel:
        """Return a configured chat model for the requested provider/model."""
        provider, model_name = LLMRouter.resolve_provider_model(
            provider,
            model_name,
        )
        settings = get_settings()

        if provider == "openai":
            return ChatOpenAI(
                model=model_name,
                api_key=settings.openai_api_key,
                max_retries=2,
                temperature=0,
            )
        if provider == "google":
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=settings.google_api_key,
                temperature=0,
            )
        if provider == "groq":
            return ChatGroq(
                model=model_name,
                api_key=settings.groq_api_key,
                max_retries=2,
                temperature=0,
            )

        msg = f"Unsupported provider: {provider}"
        raise ValueError(msg)
