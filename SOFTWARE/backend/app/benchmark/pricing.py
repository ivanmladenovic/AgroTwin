from __future__ import annotations

from app.benchmark.types import TokenUsage
from app.core.config import Settings


def estimate_cost_usd(
    provider: str,
    usage: TokenUsage,
    settings: Settings,
) -> float | None:
    """Estimate USD cost from token usage and configured per-1M rates.

    Returns None when input/output token counts are unavailable.
    Cached / special categories are ignored until pricing is configured for them.
    """
    if usage.input_tokens is None or usage.output_tokens is None:
        return None
    if provider == "gemini":
        input_rate = settings.benchmark_gemini_input_usd_per_mtok
        output_rate = settings.benchmark_gemini_output_usd_per_mtok
    elif provider == "openai":
        input_rate = settings.benchmark_openai_input_usd_per_mtok
        output_rate = settings.benchmark_openai_output_usd_per_mtok
    else:
        return None
    return round(
        (usage.input_tokens / 1_000_000) * input_rate
        + (usage.output_tokens / 1_000_000) * output_rate,
        8,
    )


def pricing_snapshot(settings: Settings) -> dict[str, dict[str, float]]:
    return {
        "gemini": {
            "input_usd_per_mtok": settings.benchmark_gemini_input_usd_per_mtok,
            "output_usd_per_mtok": settings.benchmark_gemini_output_usd_per_mtok,
        },
        "openai": {
            "input_usd_per_mtok": settings.benchmark_openai_input_usd_per_mtok,
            "output_usd_per_mtok": settings.benchmark_openai_output_usd_per_mtok,
        },
    }
