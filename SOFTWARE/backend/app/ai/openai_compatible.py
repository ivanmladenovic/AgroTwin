from __future__ import annotations

import json
import logging
import time
from typing import Any
from uuid import uuid4

import httpx

from app.ai.base import ChatMessage, ChatResult, ImageAnalysisResult, ToolCall, ToolSpec
from app.ai.prompts import ANALYSIS_DISCLAIMER
from app.core.config import Settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

# When Google returns 503 high-demand on a primary Gemini chat model, try these next.
_GEMINI_CHAT_FALLBACKS = (
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-flash-latest",
)

# After a capacity fallback succeeds, keep using that model for a while (avoids 503 tax every tool round).
_STICKY_TTL_SEC = 600.0
_sticky_model: str | None = None
_sticky_until: float = 0.0


def _get_sticky_model() -> str | None:
    global _sticky_model, _sticky_until
    if _sticky_model and time.monotonic() < _sticky_until:
        return _sticky_model
    _sticky_model = None
    _sticky_until = 0.0
    return None


def _set_sticky_model(model: str) -> None:
    global _sticky_model, _sticky_until
    _sticky_model = model
    _sticky_until = time.monotonic() + _STICKY_TTL_SEC
    logger.info("AI chat sticky model set to %s for %.0fs", model, _STICKY_TTL_SEC)


def _clear_sticky_model() -> None:
    global _sticky_model, _sticky_until
    if _sticky_model:
        logger.info("AI chat sticky model cleared (%s)", _sticky_model)
    _sticky_model = None
    _sticky_until = 0.0


class OpenAICompatibleProvider:
    """Chat, embeddings and vision via an OpenAI-compatible HTTP API.

    Configure with AI_API_KEY, AI_BASE_URL and model names. The same class
    can target OpenAI, Groq, Azure-compatible gateways or a local server.
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

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec] | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> ChatResult:
        base_payload: dict[str, Any] = {
            "messages": [_dump_message(item) for item in messages],
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
        for model in _chat_model_candidates(self.chat_model, self.base_url):
            payload = {**base_payload, "model": model}
            try:
                data = self._post("/chat/completions", payload)
                used_model = model
                if model != self.chat_model:
                    logger.warning(
                        "AI chat fell back from %s to %s after provider overload",
                        self.chat_model,
                        model,
                    )
                    _set_sticky_model(model)
                elif _get_sticky_model() == model:
                    # Refresh sticky window while the preferred fallback keeps working.
                    _set_sticky_model(model)
                break
            except AppError as exc:
                if _is_capacity_error(exc):
                    logger.warning("AI chat model %s unavailable (%s); trying fallback", model, exc.message[:120])
                    if _get_sticky_model() == model:
                        _clear_sticky_model()
                    last_error = exc
                    continue
                raise
        if data is None:
            raise last_error or AppError("AI provajder nije dostupan", status_code=502, code="ai_unavailable")

        choice = (data.get("choices") or [{}])[0].get("message") or {}
        tool_calls = []
        for raw in choice.get("tool_calls") or []:
            function = raw.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            extra = raw.get("extra_content")
            tool_calls.append(
                ToolCall(
                    id=raw.get("id") or f"call-{uuid4().hex[:8]}",
                    name=function.get("name") or "",
                    arguments=arguments if isinstance(arguments, dict) else {},
                    extra_content=extra if isinstance(extra, dict) else None,
                )
            )
        return ChatResult(
            content=choice.get("content") or "",
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
        data = self._post("/embeddings", payload)
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
        data = self._post("/embeddings", payload)
        rows = sorted(data.get("data") or [], key=lambda item: item.get("index", 0))
        return [
            _trim_embedding(list(item.get("embedding") or []), self.embedding_dim)
            for item in rows
        ]

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.base_url}{path}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
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


def _chat_model_candidates(primary: str, base_url: str) -> list[str]:
    models: list[str] = []
    sticky = _get_sticky_model()
    if sticky:
        models.append(sticky)
    if primary not in models:
        models.append(primary)
    if "generativelanguage.googleapis.com" in base_url or primary.startswith("gemini"):
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
    )


def _dump_message(message: ChatMessage) -> dict[str, Any]:
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
            if item.extra_content:
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
