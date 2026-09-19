from functools import lru_cache

from app.ai.base import AIProvider
from app.ai.local import LocalAIProvider
from app.ai.openai_compatible import OpenAICompatibleProvider
from app.core.config import get_settings
from app.core.exceptions import AppError


@lru_cache
def get_ai_provider() -> AIProvider:
    settings = get_settings()
    name = (settings.ai_provider or "local").strip().lower()
    if name in {"local", "dev", "deterministic"}:
        return LocalAIProvider(settings)
    if name in {"openai", "openai_compatible", "openai-compatible"}:
        return OpenAICompatibleProvider(settings)
    raise AppError(
        f"Nepoznat AI_PROVIDER '{settings.ai_provider}'. Koristite local ili openai_compatible.",
        status_code=500,
        code="ai_provider_unknown",
    )


def reset_ai_provider() -> None:
    get_ai_provider.cache_clear()
