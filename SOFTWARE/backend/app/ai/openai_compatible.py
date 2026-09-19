from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import httpx

from app.ai.base import ChatMessage, ChatResult, ImageAnalysisResult, ToolCall, ToolSpec
from app.ai.prompts import ANALYSIS_DISCLAIMER
from app.core.config import Settings
from app.core.exceptions import AppError


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
        self.timeout = 60.0

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec] | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self.chat_model,
            "messages": [_dump_message(item) for item in messages],
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = [
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
            payload["tool_choice"] = "auto"
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = self._post("/chat/completions", payload)
        choice = (data.get("choices") or [{}])[0].get("message") or {}
        tool_calls = []
        for raw in choice.get("tool_calls") or []:
            function = raw.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(
                    id=raw.get("id") or f"call-{uuid4().hex[:8]}",
                    name=function.get("name") or "",
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )
        return ChatResult(
            content=choice.get("content") or "",
            tool_calls=tool_calls,
            model=data.get("model") or self.chat_model,
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
        data = self._post("/embeddings", {"model": self.embedding_model, "input": text})
        return list((data.get("data") or [{}])[0].get("embedding") or [])

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = self._post("/embeddings", {"model": self.embedding_model, "input": texts})
        rows = sorted(data.get("data") or [], key=lambda item: item.get("index", 0))
        return [list(item.get("embedding") or []) for item in rows]

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


def _dump_message(message: ChatMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_call_id:
        payload["tool_call_id"] = message.tool_call_id
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": item.id,
                "type": "function",
                "function": {"name": item.name, "arguments": json.dumps(item.arguments)},
            }
            for item in message.tool_calls
        ]
    return payload


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
