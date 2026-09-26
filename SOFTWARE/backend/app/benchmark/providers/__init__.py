from __future__ import annotations

from typing import Protocol

from app.benchmark.types import BenchmarkImage, GenerationSettings, ProviderResult


class BenchmarkProvider(Protocol):
    """Independent LLM/vision provider used only by the developer benchmark."""

    provider_id: str
    display_name: str
    model: str

    def is_configured(self) -> bool: ...

    def generate(
        self,
        *,
        system_instruction: str,
        user_text: str,
        image: BenchmarkImage | None,
        settings: GenerationSettings,
    ) -> ProviderResult: ...
