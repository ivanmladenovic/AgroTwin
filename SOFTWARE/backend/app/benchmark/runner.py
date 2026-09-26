from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from app.benchmark.message import build_user_message, mode_requires_image
from app.benchmark.pricing import estimate_cost_usd
from app.benchmark.providers.gemini import GeminiBenchmarkProvider
from app.benchmark.providers.openai import OpenAIBenchmarkProvider
from app.benchmark.types import (
    BenchmarkInput,
    BenchmarkResult,
    GenerationSettings,
    ProviderId,
    ProviderResult,
)
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

EQUIVALENCE_NOTES = [
    "Identical system instruction, user text, and image bytes are sent to every selected provider.",
    "No provider-specific prompt rewriting is applied.",
    "Web search / grounding tools are disabled for both providers.",
    "Token controls differ slightly: Gemini uses maxOutputTokens; OpenAI uses max_completion_tokens.",
    "Gemini may apply thinkingLevel=low; OpenAI may ignore temperature on some reasoning models.",
]


def run_benchmark(payload: BenchmarkInput, settings: Settings | None = None) -> BenchmarkResult:
    settings = settings or get_settings()
    if not payload.prompt.strip():
        raise AppError("Prompt je obavezan", status_code=422, code="invalid_prompt")
    if not payload.providers:
        raise AppError("Izaberite bar jedan model", status_code=422, code="no_providers")

    requires_image = mode_requires_image(payload.mode)
    if requires_image and payload.image is None:
        raise AppError(
            f"Režim '{payload.mode.value}' zahteva sliku",
            status_code=422,
            code="image_required",
        )

    gen = payload.settings or GenerationSettings(
        temperature=settings.benchmark_temperature,
        max_output_tokens=settings.benchmark_max_output_tokens,
    )
    user_text = build_user_message(
        prompt=payload.prompt,
        mode=payload.mode,
        context=payload.context,
        knowledge_evidence=payload.knowledge_evidence,
        has_image=payload.image is not None,
    )

    providers = _resolve_providers(payload.providers, settings)
    results: list[ProviderResult] = []

    # Run selected providers in parallel; isolate failures per provider.
    with ThreadPoolExecutor(max_workers=max(1, len(providers))) as pool:
        futures = {
            pool.submit(
                _safe_generate,
                provider,
                system_instruction=payload.system_instruction,
                user_text=user_text,
                image=payload.image,
                settings=gen,
                app_settings=settings,
            ): provider.provider_id
            for provider in providers
        }
        by_id: dict[str, ProviderResult] = {}
        for future in as_completed(futures):
            provider_id = futures[future]
            by_id[provider_id] = future.result()
        for provider in providers:
            results.append(by_id[provider.provider_id])

    logger.info(
        "benchmark_run test_name=%s mode=%s providers=%s statuses=%s",
        payload.test_name,
        payload.mode.value,
        [item.provider for item in results],
        [item.status for item in results],
    )

    return BenchmarkResult(
        test_name=payload.test_name or "Untitled test",
        mode=payload.mode,
        has_image=payload.image is not None,
        prompt_preview=payload.prompt[:240],
        system_instruction=payload.system_instruction,
        generation_settings={
            "temperature": gen.temperature,
            "max_output_tokens": gen.max_output_tokens,
            **gen.extras,
        },
        equivalence_notes=list(EQUIVALENCE_NOTES),
        results=results,
        ran_at=datetime.now(timezone.utc),
    )


def _resolve_providers(selected: list[ProviderId], settings: Settings):
    mapping = {
        ProviderId.GEMINI: GeminiBenchmarkProvider(settings),
        ProviderId.OPENAI: OpenAIBenchmarkProvider(settings),
    }
    return [mapping[item] for item in selected]


def _safe_generate(provider, *, system_instruction, user_text, image, settings, app_settings) -> ProviderResult:
    try:
        result = provider.generate(
            system_instruction=system_instruction,
            user_text=user_text,
            image=image,
            settings=settings,
        )
    except Exception as exc:  # noqa: BLE001 — isolate unexpected provider bugs
        started = datetime.now(timezone.utc)
        logger.exception(
            "benchmark_provider_crash provider=%s model=%s",
            getattr(provider, "provider_id", "?"),
            getattr(provider, "model", "?"),
        )
        return ProviderResult(
            provider=getattr(provider, "provider_id", "unknown"),
            model=getattr(provider, "model", "unknown"),
            status="error",
            started_at=started,
            ended_at=started,
            latency_ms=0,
            error_code="provider_crash",
            error_message=f"Neočekivana greška provajdera: {type(exc).__name__}",
            generation_settings={
                "temperature": settings.temperature,
                "max_output_tokens": settings.max_output_tokens,
            },
        )
    if result.estimated_cost_usd is None and result.status == "success":
        result.estimated_cost_usd = estimate_cost_usd(result.provider, result.usage, app_settings)
    return result
