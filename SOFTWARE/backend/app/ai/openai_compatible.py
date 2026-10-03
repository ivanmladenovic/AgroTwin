from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from app.ai.base import ChatMessage, ChatResult, ImageAnalysisResult, ToolCall, ToolSpec
from app.ai.prompts import ANALYSIS_DISCLAIMER
from app.core.config import Settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

# Same-provider Gemini retries after the configured primary model.
# Keep this short — long Gemini cascades delay OpenAI fallback and stress free hosts.
_GEMINI_CHAT_FALLBACKS = (
    "gemini-3.8-flash",
    "gemini-flash-latest",
)

_DEFAULT_OPENAI_FALLBACKS = ("gpt-4.1-mini", "gpt-4o")

# After a capacity fallback succeeds, keep using that endpoint/model briefly.
_STICKY_TTL_SEC = 600.0
_sticky_endpoint: str | None = None
_sticky_model: str | None = None
_sticky_until: float = 0.0

# If Gemini capacity fails repeatedly, skip Gemini for a while and go straight to OpenAI.
_CIRCUIT_FAIL_THRESHOLD = 2
_CIRCUIT_OPEN_SEC = 900.0
_gemini_fail_streak = 0
_gemini_circuit_until = 0.0


@dataclass(frozen=True)
class _ChatTarget:
    base_url: str
    api_key: str
    model: str
    provider_label: str


def _get_sticky() -> tuple[str, str] | None:
    global _sticky_endpoint, _sticky_model, _sticky_until
    if _sticky_endpoint and _sticky_model and time.monotonic() < _sticky_until:
        return _sticky_endpoint, _sticky_model
    _sticky_endpoint = None
    _sticky_model = None
    _sticky_until = 0.0
    return None


def _set_sticky(base_url: str, model: str) -> None:
    global _sticky_endpoint, _sticky_model, _sticky_until
    _sticky_endpoint = base_url.rstrip("/")
    _sticky_model = model
    _sticky_until = time.monotonic() + _STICKY_TTL_SEC
    logger.info("AI chat sticky set to %s @ %s for %.0fs", model, _sticky_endpoint, _STICKY_TTL_SEC)


def _clear_sticky() -> None:
    global _sticky_endpoint, _sticky_model, _sticky_until
    if _sticky_model:
        logger.info("AI chat sticky cleared (%s)", _sticky_model)
    _sticky_endpoint = None
    _sticky_model = None
    _sticky_until = 0.0


def _gemini_circuit_open() -> bool:
    return time.monotonic() < _gemini_circuit_until


def _record_gemini_success() -> None:
    global _gemini_fail_streak, _gemini_circuit_until
    _gemini_fail_streak = 0
    _gemini_circuit_until = 0.0


def _record_gemini_capacity_failure() -> None:
    global _gemini_fail_streak, _gemini_circuit_until
    _gemini_fail_streak += 1
    if _gemini_fail_streak >= _CIRCUIT_FAIL_THRESHOLD:
        _gemini_circuit_until = time.monotonic() + _CIRCUIT_OPEN_SEC
        logger.warning(
            "AI Gemini circuit open for %.0fs after %s capacity failures",
            _CIRCUIT_OPEN_SEC,
            _gemini_fail_streak,
        )


def _reset_runtime_state() -> None:
    """Test helper — clear sticky + circuit breaker."""
    global _gemini_fail_streak, _gemini_circuit_until
    _clear_sticky()
    _gemini_fail_streak = 0
    _gemini_circuit_until = 0.0


def _is_gemini_endpoint(base_url: str) -> bool:
    return "generativelanguage.googleapis.com" in (base_url or "")


class OpenAICompatibleProvider:
    """Chat, embeddings and vision via an OpenAI-compatible HTTP API.

    Primary endpoint is usually Gemini. When Gemini is overloaded, the same
    chat/vision path can fall through to OpenAI models (OPENAI_API_KEY).
    """

    name = "openai_compatible"

    def __init__(self, settings: Settings) -> None:
        if not settings.ai_api_key:
            raise AppError(
                "AI_API_KEY is not set. Use AI_PROVIDER=local or configure an OpenAI-compatible key.",
                status_code=503,
                code="ai_not_configured",
            )
        self.api_key = settings.ai_api_key
        self.base_url = settings.ai_base_url.rstrip("/")
        self.chat_model = settings.ai_chat_model
        self.embedding_model = settings.ai_embedding_model
        self.vision_model = settings.ai_vision_model or settings.ai_chat_model
        self.embedding_dim = settings.ai_embedding_dim
        self.timeout = 60.0
        self.openai_api_key = (settings.openai_api_key or "").strip() or None
        self.openai_base_url = (settings.ai_openai_base_url or "https://api.openai.com/v1").rstrip("/")
        self.openai_fallback_models = _parse_model_list(
            settings.ai_openai_fallback_models,
            default=_DEFAULT_OPENAI_FALLBACKS,
        )

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec] | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> ChatResult:
        base_payload: dict[str, Any] = {
            "temperature": temperature,
        }
        if tools:
            base_payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": item.name,
                        "description": item.description,
                        "parameters": item.parameters,
                    },
                }
                for item in tools
            ]
            base_payload["tool_choice"] = "auto"
        if json_mode:
            base_payload["response_format"] = {"type": "json_object"}

        last_error: AppError | None = None
        data: dict[str, Any] | None = None
        used_model = self.chat_model
        used_label = "primary"
        targets = self._chat_targets()
        if not self.openai_api_key:
            logger.warning("AI OpenAI fallback disabled — OPENAI_API_KEY is not set")
        logger.info(
            "AI chat trying %s target(s): %s",
            len(targets),
            ", ".join(f"{t.provider_label}/{t.model}" for t in targets),
        )
        # After one Gemini capacity miss, jump to OpenAI instead of waiting on more Gemini 503s.
        skip_remaining_gemini = False
        for index, target in enumerate(targets):
            if skip_remaining_gemini and target.provider_label == "gemini":
                logger.info(
                    "AI chat skipping %s/%s after Gemini capacity error (OpenAI available)",
                    target.provider_label,
                    target.model,
                )
                continue
            logger.info(
                "AI chat attempt %s/%s → %s/%s",
                index + 1,
                len(targets),
                target.provider_label,
                target.model,
            )
            payload = {
                **base_payload,
                "model": target.model,
                "messages": [
                    _dump_message(item, include_extra=target.provider_label == "gemini")
                    for item in messages
                ],
            }
            try:
                data = self._post(target.base_url, target.api_key, "/chat/completions", payload)
                used_model = target.model
                used_label = target.provider_label
                if target.model != self.chat_model or target.base_url != self.base_url:
                    logger.warning(
                        "AI chat fell back to %s/%s after provider overload",
                        target.provider_label,
                        target.model,
                    )
                else:
                    logger.info("AI chat succeeded with %s/%s", target.provider_label, target.model)
                _set_sticky(target.base_url, target.model)
                if target.provider_label == "gemini":
                    _record_gemini_success()
                break
            except AppError as exc:
                if _is_capacity_error(exc):
                    remaining = len(targets) - index - 1
                    logger.warning(
                        "AI chat target %s/%s unavailable (%s); %s left",
                        target.provider_label,
                        target.model,
                        exc.message[:120].replace("\n", " "),
                        remaining,
                    )
                    sticky = _get_sticky()
                    if sticky and sticky[0] == target.base_url.rstrip("/") and sticky[1] == target.model:
                        _clear_sticky()
                    if target.provider_label == "gemini":
                        _record_gemini_capacity_failure()
                        if self.openai_api_key:
                            skip_remaining_gemini = True
                    last_error = exc
                    continue
                raise
        if data is None:
            logger.error(
                "AI chat exhausted all %s target(s); last error: %s",
                len(targets),
                (last_error.message[:200] if last_error else "none"),
            )
            raise last_error or AppError(
                "AI servis trenutno nije dostupan. Pokušajte ponovo za minut-dva.",
                status_code=502,
                code="ai_unavailable",
            )

        choice = (data.get("choices") or [{}])[0].get("message") or {}
        tool_calls = []
        for raw in choice.get("tool_calls") or []:
            function = raw.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            extra = raw.get("extra_content") if used_label == "gemini" else None
            tool_calls.append(
                ToolCall(
                    id=raw.get("id") or f"call-{uuid4().hex[:8]}",
                    name=function.get("name") or "",
                    arguments=arguments if isinstance(arguments, dict) else {},
                    extra_content=extra if isinstance(extra, dict) else None,
                )
            )
        content = _message_text(choice.get("content"))
        if not content and not tool_calls:
            content = _message_text(choice.get("refusal")) or _message_text(
                (data.get("choices") or [{}])[0].get("text")
            )
        return ChatResult(
            content=content,
            tool_calls=tool_calls,
            model=data.get("model") or used_model,
            raw=data,
        )

    def analyze_image(
        self,
        image: bytes,
        mime_type: str,
        prompt: str,
        *,
        json_mode: bool = True,
    ) -> ImageAnalysisResult:
        import base64

        encoded = base64.b64encode(image).decode("ascii")
        user = ChatMessage(
            role="user",
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
            ],
        )
        result = self.chat([user], json_mode=json_mode, temperature=0.1)
        payload = _parse_analysis(result.content)
        payload.model = result.model or self.vision_model
        payload.raw = result.raw
        return payload

    def generate_embedding(self, text: str) -> list[float]:
        payload: dict[str, Any] = {"model": self.embedding_model, "input": text}
        if self.embedding_dim:
            payload["dimensions"] = self.embedding_dim
        data = self._post(self.base_url, self.api_key, "/embeddings", payload)
        return _trim_embedding(
            list((data.get("data") or [{}])[0].get("embedding") or []),
            self.embedding_dim,
        )

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload: dict[str, Any] = {"model": self.embedding_model, "input": texts}
        if self.embedding_dim:
            payload["dimensions"] = self.embedding_dim
        data = self._post(self.base_url, self.api_key, "/embeddings", payload)
        rows = sorted(data.get("data") or [], key=lambda item: item.get("index", 0))
        return [
            _trim_embedding(list(item.get("embedding") or []), self.embedding_dim)
            for item in rows
        ]

    def _chat_targets(self) -> list[_ChatTarget]:
        targets: list[_ChatTarget] = []
        seen: set[tuple[str, str]] = set()

        def add(base_url: str, api_key: str, model: str, label: str) -> None:
            key = (base_url.rstrip("/"), model)
            if not api_key or not model or key in seen:
                return
            seen.add(key)
            targets.append(
                _ChatTarget(
                    base_url=base_url.rstrip("/"),
                    api_key=api_key,
                    model=model,
                    provider_label=label,
                )
            )

        sticky = _get_sticky()
        skip_gemini = _gemini_circuit_open() and bool(self.openai_api_key)

        if sticky:
            sticky_url, sticky_model = sticky
            sticky_is_gemini = _is_gemini_endpoint(sticky_url)
            if not (skip_gemini and sticky_is_gemini):
                key = self.api_key if sticky_is_gemini or sticky_url == self.base_url else (self.openai_api_key or "")
                if sticky_is_gemini:
                    key = self.api_key
                elif sticky_url.rstrip("/") == self.openai_base_url.rstrip("/"):
                    key = self.openai_api_key or ""
                else:
                    key = self.api_key
                label = "gemini" if sticky_is_gemini else "openai"
                add(sticky_url, key or "", sticky_model, label)

        if not skip_gemini:
            add(self.base_url, self.api_key, self.chat_model, "gemini" if _is_gemini_endpoint(self.base_url) else "primary")
            if _is_gemini_endpoint(self.base_url) or self.chat_model.startswith("gemini"):
                for model in _GEMINI_CHAT_FALLBACKS:
                    add(self.base_url, self.api_key, model, "gemini")
        elif sticky is None:
            logger.info("AI Gemini circuit open — trying OpenAI fallbacks first")

        if self.openai_api_key:
            for model in self.openai_fallback_models:
                add(self.openai_base_url, self.openai_api_key, model, "openai")

        # If circuit skipped Gemini and OpenAI also fails, allow one last Gemini pass.
        if skip_gemini and self.openai_api_key:
            add(self.base_url, self.api_key, self.chat_model, "gemini")
            for model in _GEMINI_CHAT_FALLBACKS:
                add(self.base_url, self.api_key, model, "gemini")

        return targets

    def _post(self, base_url: str, api_key: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{base_url.rstrip('/')}{path}",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise AppError(f"Zahtev ka AI provajderu nije uspeo: {exc}", status_code=502, code="ai_unavailable") from exc
        if response.status_code >= 400:
            raise AppError(
                f"AI provajder je vratio {response.status_code}: {response.text[:400]}",
                status_code=502,
                code="ai_unavailable",
            )
        return response.json()


def _parse_model_list(raw: str | None, *, default: tuple[str, ...]) -> tuple[str, ...]:
    if not raw or not str(raw).strip():
        return default
    items = tuple(item.strip() for item in str(raw).split(",") if item.strip())
    return items or default


def _message_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
                elif isinstance(item.get("content"), str) and item["content"].strip():
                    parts.append(item["content"].strip())
        return "\n".join(parts).strip()
    return str(value).strip()


def _chat_model_candidates(primary: str, base_url: str) -> list[str]:
    """Backward-compatible helper used by unit tests."""
    models: list[str] = []
    sticky = _get_sticky()
    if sticky:
        models.append(sticky[1])
    if primary not in models:
        models.append(primary)
    if _is_gemini_endpoint(base_url) or primary.startswith("gemini"):
        for item in _GEMINI_CHAT_FALLBACKS:
            if item not in models:
                models.append(item)
    return models


def _is_capacity_error(exc: AppError) -> bool:
    text = (exc.message or "").lower()
    return (
        "503" in text
        or "unavailable" in text
        or "high demand" in text
        or "resource_exhausted" in text
        or "429" in text
        or "rate limit" in text
        or "overloaded" in text
    )


def _dump_message(message: ChatMessage, *, include_extra: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role}
    # Gemini rejects empty-string content on tool-call assistant turns; omit or null.
    if message.tool_calls and (message.content is None or message.content == ""):
        payload["content"] = None
    else:
        payload["content"] = message.content
    if message.tool_call_id:
        payload["tool_call_id"] = message.tool_call_id
    if message.tool_calls:
        serialized = []
        for item in message.tool_calls:
            entry: dict[str, Any] = {
                "id": item.id,
                "type": "function",
                "function": {"name": item.name, "arguments": json.dumps(item.arguments)},
            }
            if include_extra and item.extra_content:
                entry["extra_content"] = item.extra_content
            serialized.append(entry)
        payload["tool_calls"] = serialized
    return payload


def _trim_embedding(vector: list[float], dim: int | None) -> list[float]:
    if not dim or len(vector) == dim:
        return vector
    if len(vector) > dim:
        return vector[:dim]
    return vector


def _parse_analysis(content: str) -> ImageAnalysisResult:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {}
    return ImageAnalysisResult(
        likely_issue=str(data.get("likely_issue") or "Neizvesno — nema dovoljno dokaza za konkretan problem"),
        confidence=float(data.get("confidence") or 0.2),
        observed_symptoms=list(data.get("observed_symptoms") or []),
        possible_alternatives=list(data.get("possible_alternatives") or []),
        recommended_inspection=str(data.get("recommended_inspection") or "Pregledajte susedna stabla i napravite još jednu datiranu fotografiju."),
        recommended_next_step=str(
            data.get("recommended_next_step")
            or "Zadržite ovo kao opažanje dok ga ne pregleda stručni savetnik."
        ),
        observed_facts=str(data.get("observed_facts") or "Dostupne su samo beleške proizvođača i otpremljena slika."),
        uncertainty_notes=str(data.get("uncertainty_notes") or "Ovo nije laboratorijska potvrda."),
        disclaimer=str(data.get("disclaimer") or ANALYSIS_DISCLAIMER),
        raw=data,
    )
