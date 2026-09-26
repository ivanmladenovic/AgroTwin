from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class BenchmarkMode(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    IMAGE_CONTEXT = "image_context"
    FULL = "full"


class ProviderId(str, Enum):
    GEMINI = "gemini"
    OPENAI = "openai"


@dataclass
class BenchmarkImage:
    content: bytes
    mime_type: str
    filename: str
    width: int | None = None
    height: int | None = None
    source: str = "upload"  # upload | photo


@dataclass
class GenerationSettings:
    temperature: float
    max_output_tokens: int
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkInput:
    test_name: str
    mode: BenchmarkMode
    prompt: str
    system_instruction: str
    context: dict[str, Any] | list[Any] | None = None
    knowledge_evidence: list[Any] | dict[str, Any] | None = None
    image: BenchmarkImage | None = None
    settings: GenerationSettings | None = None
    providers: list[ProviderId] = field(default_factory=lambda: [ProviderId.GEMINI, ProviderId.OPENAI])


@dataclass
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_input_tokens: int | None = None


@dataclass
class ProviderResult:
    provider: str
    model: str
    status: str  # success | error
    started_at: datetime
    ended_at: datetime
    latency_ms: int
    response_text: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    estimated_cost_usd: float | None = None
    generation_settings: dict[str, Any] = field(default_factory=dict)
    metadata_notes: list[str] = field(default_factory=list)
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    test_name: str
    mode: BenchmarkMode
    has_image: bool
    prompt_preview: str
    system_instruction: str
    generation_settings: dict[str, Any]
    equivalence_notes: list[str]
    results: list[ProviderResult]
    ran_at: datetime
