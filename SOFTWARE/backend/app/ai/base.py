from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ChatMessage:
    role: str
    content: str | list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResult:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageAnalysisResult:
    likely_issue: str
    confidence: float
    observed_symptoms: list[str]
    possible_alternatives: list[str]
    recommended_inspection: str
    recommended_next_step: str
    observed_facts: str
    uncertainty_notes: str
    disclaimer: str
    model: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class AIProvider(Protocol):
    """LLM access is always behind this interface.

    Swap OpenAI-compatible APIs, a local fallback, or a later vendor
    without changing agronomist or knowledge services.
    """

    name: str
    chat_model: str
    embedding_model: str
    vision_model: str

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec] | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> ChatResult: ...

    def analyze_image(
        self,
        image: bytes,
        mime_type: str,
        prompt: str,
        *,
        json_mode: bool = True,
    ) -> ImageAnalysisResult: ...

    def generate_embedding(self, text: str) -> list[float]: ...

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self.generate_embedding(text) for text in texts]
