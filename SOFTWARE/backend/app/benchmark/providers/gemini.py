from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.benchmark.pricing import estimate_cost_usd
from app.benchmark.types import BenchmarkImage, GenerationSettings, ProviderResult, TokenUsage
from app.core.config import Settings

logger = logging.getLogger(__name__)

_SECRET_RE = re.compile(r"(api[_-]?key|authorization|bearer)\s*[:=]\s*\S+", re.I)


def sanitize_error_text(text: str, *, max_len: int = 400) -> str:
    cleaned = _SECRET_RE.sub(r"\1=[redacted]", text or "")
    return cleaned[:max_len]


class GeminiBenchmarkProvider:
    provider_id = "gemini"
    display_name = "Gemini 3.8 Flash"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model
        self.base_url = settings.gemini_base_url.rstrip("/")
        self.timeout = settings.benchmark_timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate(
        self,
        *,
        system_instruction: str,
        user_text: str,
        image: BenchmarkImage | None,
        settings: GenerationSettings,
    ) -> ProviderResult:
        started = datetime.now(timezone.utc)
        gen_settings = {
            "temperature": settings.temperature,
            "max_output_tokens": settings.max_output_tokens,
            **settings.extras,
            "web_search": False,
            "google_search_grounding": False,
        }
        notes = [
            "Google Search / grounding tools are not attached to this request.",
            "Gemini thinkingConfig uses thinkingLevel=low when supported by the model API.",
        ]
        if not self.api_key:
            ended = datetime.now(timezone.utc)
            return ProviderResult(
                provider=self.provider_id,
                model=self.model,
                status="error",
                started_at=started,
                ended_at=ended,
                latency_ms=_latency_ms(started, ended),
                error_code="missing_api_key",
                error_message="GEMINI_API_KEY nije podešen na serveru",
                generation_settings=gen_settings,
                metadata_notes=notes,
            )

        parts: list[dict[str, Any]] = [{"text": user_text}]
        if image is not None:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": image.mime_type,
                        "data": base64.b64encode(image.content).decode("ascii"),
                    }
                }
            )
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": settings.temperature,
                "maxOutputTokens": settings.max_output_tokens,
                "thinkingConfig": {"thinkingLevel": "low"},
            },
        }
        # Intentionally omit tools — no googleSearch / grounding.

        url = f"{self.base_url}/models/{self.model}:generateContent"
        try:
            response = httpx.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.api_key,
                },
                json=payload,
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            return self._error(started, gen_settings, notes, "timeout", "Zahtev ka Gemini API-ju je istekao", exc)
        except httpx.HTTPError as exc:
            return self._error(
                started,
                gen_settings,
                notes,
                "provider_unavailable",
                f"Zahtev ka Gemini API-ju nije uspeo: {sanitize_error_text(str(exc))}",
                exc,
            )

        ended = datetime.now(timezone.utc)
        if response.status_code >= 400:
            code, message = _classify_http_error(response.status_code, response.text)
            logger.warning(
                "benchmark_provider_error provider=gemini model=%s status=%s code=%s",
                self.model,
                response.status_code,
                code,
            )
            return ProviderResult(
                provider=self.provider_id,
                model=self.model,
                status="error",
                started_at=started,
                ended_at=ended,
                latency_ms=_latency_ms(started, ended),
                error_code=code,
                error_message=message,
                generation_settings=gen_settings,
                metadata_notes=notes,
                raw_metadata={"http_status": response.status_code},
            )

        data = response.json()
        text = _extract_gemini_text(data)
        usage = _extract_gemini_usage(data)
        cost = estimate_cost_usd(self.provider_id, usage, self.settings)
        logger.info(
            "benchmark_provider_ok provider=gemini model=%s latency_ms=%s input_tokens=%s output_tokens=%s",
            self.model,
            _latency_ms(started, ended),
            usage.input_tokens,
            usage.output_tokens,
        )
        return ProviderResult(
            provider=self.provider_id,
            model=data.get("modelVersion") or self.model,
            status="success",
            started_at=started,
            ended_at=ended,
            latency_ms=_latency_ms(started, ended),
            response_text=text,
            usage=usage,
            estimated_cost_usd=cost,
            generation_settings=gen_settings,
            metadata_notes=notes,
            raw_metadata=_safe_raw(data),
        )

    def _error(
        self,
        started: datetime,
        gen_settings: dict[str, Any],
        notes: list[str],
        code: str,
        message: str,
        exc: Exception,
    ) -> ProviderResult:
        ended = datetime.now(timezone.utc)
        logger.warning(
            "benchmark_provider_error provider=gemini model=%s code=%s err=%s",
            self.model,
            code,
            type(exc).__name__,
        )
        return ProviderResult(
            provider=self.provider_id,
            model=self.model,
            status="error",
            started_at=started,
            ended_at=ended,
            latency_ms=_latency_ms(started, ended),
            error_code=code,
            error_message=message,
            generation_settings=gen_settings,
            metadata_notes=notes,
        )


def _extract_gemini_text(data: dict[str, Any]) -> str:
    chunks: list[str] = []
    for candidate in data.get("candidates") or []:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if text:
                chunks.append(str(text))
    return "\n".join(chunks).strip()


def _extract_gemini_usage(data: dict[str, Any]) -> TokenUsage:
    meta = data.get("usageMetadata") or {}
    input_tokens = meta.get("promptTokenCount")
    output_tokens = meta.get("candidatesTokenCount")
    total = meta.get("totalTokenCount")
    reasoning = meta.get("thoughtsTokenCount")
    cached = meta.get("cachedContentTokenCount")
    return TokenUsage(
        input_tokens=int(input_tokens) if input_tokens is not None else None,
        output_tokens=int(output_tokens) if output_tokens is not None else None,
        total_tokens=int(total) if total is not None else None,
        reasoning_tokens=int(reasoning) if reasoning is not None else None,
        cached_input_tokens=int(cached) if cached is not None else None,
    )


def _safe_raw(data: dict[str, Any]) -> dict[str, Any]:
    """Keep response metadata without dumping huge inline image echoes."""
    usage = data.get("usageMetadata")
    candidates = data.get("candidates") or []
    finish = None
    if candidates:
        finish = candidates[0].get("finishReason")
    return {
        "usageMetadata": usage,
        "finishReason": finish,
        "modelVersion": data.get("modelVersion"),
    }


def _classify_http_error(status: int, body: str) -> tuple[str, str]:
    text = sanitize_error_text(body)
    if status in {401, 403}:
        return "invalid_api_key", "Gemini API ključ je neispravan ili nema dozvolu"
    if status == 429:
        return "rate_limit", "Gemini API je vratio rate limit"
    if status == 400:
        return "invalid_request", f"Gemini je odbio zahtev: {text}"
    return "provider_error", f"Gemini API greška ({status}): {text}"


def _latency_ms(started: datetime, ended: datetime) -> int:
    return max(0, int((ended - started).total_seconds() * 1000))
