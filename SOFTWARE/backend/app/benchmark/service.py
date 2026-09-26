from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.benchmark.image import validate_benchmark_image
from app.benchmark.prompts import BENCHMARK_SYSTEM_INSTRUCTION
from app.benchmark.rate_limit import rate_limiter
from app.benchmark.runner import run_benchmark
from app.benchmark.test_cases import PRESET_TEST_CASES
from app.benchmark.types import (
    BenchmarkInput,
    BenchmarkMode,
    BenchmarkResult,
    GenerationSettings,
    ProviderId,
)
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.services.disease import DiseaseService

logger = logging.getLogger(__name__)


class BenchmarkService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.diseases = DiseaseService(db)

    def public_config(self) -> dict[str, Any]:
        s = self.settings
        return {
            "models": [
                {
                    "id": "gemini",
                    "provider": "gemini",
                    "display_name": "Gemini 3.8 Flash",
                    "model_id": s.gemini_model,
                    "configured": bool(s.gemini_api_key),
                },
                {
                    "id": "openai",
                    "provider": "openai",
                    "display_name": "GPT-5",
                    "model_id": s.openai_benchmark_model,
                    "configured": bool(s.openai_api_key),
                },
            ],
            "defaults": {
                "temperature": s.benchmark_temperature,
                "max_output_tokens": s.benchmark_max_output_tokens,
                "system_instruction": BENCHMARK_SYSTEM_INSTRUCTION,
                "max_image_bytes": s.benchmark_max_image_bytes,
                "max_image_edge": s.benchmark_max_image_edge,
                "rate_limit_per_minute": s.benchmark_rate_limit_per_minute,
            },
            "pricing": {
                "gemini": {
                    "input_usd_per_mtok": s.benchmark_gemini_input_usd_per_mtok,
                    "output_usd_per_mtok": s.benchmark_gemini_output_usd_per_mtok,
                },
                "openai": {
                    "input_usd_per_mtok": s.benchmark_openai_input_usd_per_mtok,
                    "output_usd_per_mtok": s.benchmark_openai_output_usd_per_mtok,
                },
            },
            "modes": [item.value for item in BenchmarkMode],
            "test_cases": PRESET_TEST_CASES,
            # Never expose API keys.
        }

    def run(
        self,
        *,
        owner_id: UUID,
        test_name: str,
        mode: str,
        prompt: str,
        providers: list[str],
        context_json: str | None,
        knowledge_evidence_json: str | None,
        system_instruction: str | None,
        temperature: float | None,
        max_output_tokens: int | None,
        image_bytes: bytes | None,
        image_filename: str | None,
        image_content_type: str | None,
        photo_id: UUID | None,
    ) -> BenchmarkResult:
        rate_limiter.check(owner_id, self.settings)

        try:
            mode_enum = BenchmarkMode(mode)
        except ValueError as exc:
            raise AppError("Nepoznat režim testa", status_code=422, code="invalid_mode") from exc

        provider_ids = _parse_providers(providers)
        context = _parse_optional_json(context_json, field="context")
        knowledge = _parse_optional_json(knowledge_evidence_json, field="knowledge_evidence")

        image = None
        if photo_id is not None:
            photo = self.diseases.get_photo(photo_id, owner_id)
            content, mime = self.diseases.photo_bytes(photo)
            image = validate_benchmark_image(
                content,
                mime_type=mime,
                filename=photo.original_filename or "photo.jpg",
                settings=self.settings,
                source="photo",
            )
        elif image_bytes is not None:
            image = validate_benchmark_image(
                image_bytes,
                mime_type=image_content_type,
                filename=image_filename or "upload.jpg",
                settings=self.settings,
                source="upload",
            )

        settings = GenerationSettings(
            temperature=float(temperature) if temperature is not None else self.settings.benchmark_temperature,
            max_output_tokens=int(max_output_tokens)
            if max_output_tokens is not None
            else self.settings.benchmark_max_output_tokens,
        )
        if settings.max_output_tokens < 16 or settings.max_output_tokens > 8192:
            raise AppError(
                "max_output_tokens mora biti između 16 i 8192",
                status_code=422,
                code="invalid_settings",
            )

        payload = BenchmarkInput(
            test_name=(test_name or "").strip() or "Untitled test",
            mode=mode_enum,
            prompt=prompt or "",
            system_instruction=(system_instruction or "").strip() or BENCHMARK_SYSTEM_INSTRUCTION,
            context=context,
            knowledge_evidence=knowledge,
            image=image,
            settings=settings,
            providers=provider_ids,
        )
        return run_benchmark(payload, self.settings)


def _parse_providers(raw: list[str]) -> list[ProviderId]:
    if not raw:
        raise AppError("Izaberite bar jedan model", status_code=422, code="no_providers")
    out: list[ProviderId] = []
    seen: set[ProviderId] = set()
    for item in raw:
        key = (item or "").strip().lower()
        if key in {"gemini", "gemini-3.8-flash"}:
            pid = ProviderId.GEMINI
        elif key in {"openai", "gpt-5", "gpt5"}:
            pid = ProviderId.OPENAI
        else:
            raise AppError(f"Nepoznat provajder: {item}", status_code=422, code="invalid_provider")
        if pid not in seen:
            seen.add(pid)
            out.append(pid)
    return out


def _parse_optional_json(raw: str | None, *, field: str) -> Any | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AppError(
            f"Neispravan JSON u polju {field}: {exc.msg}",
            status_code=422,
            code="invalid_json",
        ) from exc
