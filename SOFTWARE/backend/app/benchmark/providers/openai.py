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

_SECRET_RE = re.compile(r"(api[_-]?key|authorization|bearer|sk-[A-Za-z0-9]+)", re.I)


def sanitize_error_text(text: str, *, max_len: int = 400) -> str:
    cleaned = _SECRET_RE.sub("[redacted]", text or "")
    return cleaned[:max_len]


class OpenAIBenchmarkProvider:
    provider_id = "openai"
    display_name = "GPT-5"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.openai_api_key
        self.model = settings.openai_benchmark_model
        self.base_url = settings.openai_benchmark_base_url.rstrip("/")
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
            "max_completion_tokens": settings.max_output_tokens,
            **settings.extras,
            "web_search": False,
            "tools": [],
        }
        notes = [
            "OpenAI tools / web_search are not enabled for this benchmark.",
            "Request uses max_completion_tokens (GPT-5 style); temperature may be ignored by some reasoning models.",
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
                error_message="OPENAI_API_KEY nije podešen na serveru",
                generation_settings=gen_settings,
                metadata_notes=notes,
            )

        user_content: str | list[dict[str, Any]]
        if image is None:
            user_content = user_text
        else:
            encoded = base64.b64encode(image.content).decode("ascii")
            user_content = [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image.mime_type};base64,{encoded}"},
                },
            ]

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content},
            ],
            "temperature": settings.temperature,
            "max_completion_tokens": settings.max_output_tokens,
        }
        reasoning = settings.extras.get("reasoning_effort")
        if reasoning:
            payload["reasoning_effort"] = reasoning
            notes.append(f"reasoning_effort={reasoning}")

        url = f"{self.base_url}/chat/completions"
        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            return self._error(started, gen_settings, notes, "timeout", "Zahtev ka OpenAI API-ju je istekao", exc)
        except httpx.HTTPError as exc:
            return self._error(
                started,
                gen_settings,
                notes,
                "provider_unavailable",
                f"Zahtev ka OpenAI API-ju nije uspeo: {sanitize_error_text(str(exc))}",
                exc,
            )

        ended = datetime.now(timezone.utc)
        if response.status_code >= 400:
            code, message = _classify_http_error(response.status_code, response.text)
            logger.warning(
                "benchmark_provider_error provider=openai model=%s status=%s code=%s",
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
        text = _extract_openai_text(data)
        usage = _extract_openai_usage(data)
        cost = estimate_cost_usd(self.provider_id, usage, self.settings)
        logger.info(
            "benchmark_provider_ok provider=openai model=%s latency_ms=%s input_tokens=%s output_tokens=%s",
            self.model,
            _latency_ms(started, ended),
            usage.input_tokens,
            usage.output_tokens,
        )
        return ProviderResult(
            provider=self.provider_id,
            model=data.get("model") or self.model,
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
            "benchmark_provider_error provider=openai model=%s code=%s err=%s",
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


def _extract_openai_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    return ""


def _extract_openai_usage(data: dict[str, Any]) -> TokenUsage:
    usage = data.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    input_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    reasoning = details.get("reasoning_tokens")
    cached = prompt_details.get("cached_tokens")
    return TokenUsage(
        input_tokens=int(input_tokens) if input_tokens is not None else None,
        output_tokens=int(output_tokens) if output_tokens is not None else None,
        total_tokens=int(total) if total is not None else None,
        reasoning_tokens=int(reasoning) if reasoning is not None else None,
        cached_input_tokens=int(cached) if cached is not None else None,
    )


def _safe_raw(data: dict[str, Any]) -> dict[str, Any]:
    usage = data.get("usage")
    choices = data.get("choices") or []
    finish = choices[0].get("finish_reason") if choices else None
    return {
        "id": data.get("id"),
        "model": data.get("model"),
        "usage": usage,
        "finish_reason": finish,
    }


def _classify_http_error(status: int, body: str) -> tuple[str, str]:
    text = sanitize_error_text(body)
    if status in {401, 403}:
        return "invalid_api_key", "OpenAI API ključ je neispravan ili nema dozvolu"
    if status == 429:
        return "rate_limit", "OpenAI API je vratio rate limit"
    if status == 400:
        return "invalid_request", f"OpenAI je odbio zahtev: {text}"
    return "provider_error", f"OpenAI API greška ({status}): {text}"


def _latency_ms(started: datetime, ended: datetime) -> int:
    return max(0, int((ended - started).total_seconds() * 1000))
