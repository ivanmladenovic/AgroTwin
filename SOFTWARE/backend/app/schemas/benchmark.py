from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BenchmarkModelInfo(BaseModel):
    id: str
    provider: str
    display_name: str
    model_id: str
    configured: bool


class BenchmarkPricingInfo(BaseModel):
    input_usd_per_mtok: float
    output_usd_per_mtok: float


class BenchmarkDefaults(BaseModel):
    temperature: float
    max_output_tokens: int
    system_instruction: str
    max_image_bytes: int
    max_image_edge: int
    rate_limit_per_minute: int


class BenchmarkConfigResponse(BaseModel):
    models: list[BenchmarkModelInfo]
    defaults: BenchmarkDefaults
    pricing: dict[str, BenchmarkPricingInfo]
    modes: list[str]
    test_cases: list[dict[str, Any]]


class TokenUsageRead(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_input_tokens: int | None = None


class ProviderResultRead(BaseModel):
    provider: str
    model: str
    status: str
    started_at: datetime
    ended_at: datetime
    latency_ms: int
    response_text: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    usage: TokenUsageRead = Field(default_factory=TokenUsageRead)
    estimated_cost_usd: float | None = None
    generation_settings: dict[str, Any] = Field(default_factory=dict)
    metadata_notes: list[str] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkRunResponse(BaseModel):
    test_name: str
    mode: str
    has_image: bool
    prompt_preview: str
    system_instruction: str
    generation_settings: dict[str, Any]
    equivalence_notes: list[str]
    results: list[ProviderResultRead]
    ran_at: datetime
