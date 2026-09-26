from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import CurrentSuperuser, DBSession
from app.benchmark.service import BenchmarkService
from app.benchmark.types import BenchmarkResult, ProviderResult, TokenUsage
from app.schemas.benchmark import (
    BenchmarkConfigResponse,
    BenchmarkRunResponse,
    ProviderResultRead,
    TokenUsageRead,
)

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.get("/config", response_model=BenchmarkConfigResponse)
def get_benchmark_config(current_user: CurrentSuperuser, db: DBSession) -> BenchmarkConfigResponse:
    del current_user
    return BenchmarkConfigResponse.model_validate(BenchmarkService(db).public_config())


@router.post("/run", response_model=BenchmarkRunResponse)
async def run_benchmark_comparison(
    current_user: CurrentSuperuser,
    db: DBSession,
    test_name: str = Form("Untitled test"),
    mode: str = Form("text"),
    prompt: str = Form(...),
    providers: str = Form("gemini,openai"),
    context_json: str | None = Form(None),
    knowledge_evidence_json: str | None = Form(None),
    system_instruction: str | None = Form(None),
    temperature: float | None = Form(None),
    max_output_tokens: int | None = Form(None),
    photo_id: UUID | None = Form(None),
    image: UploadFile | None = File(None),
) -> BenchmarkRunResponse:
    image_bytes: bytes | None = None
    image_filename: str | None = None
    image_content_type: str | None = None
    if image is not None and image.filename:
        image_bytes = await image.read()
        image_filename = image.filename
        image_content_type = image.content_type

    provider_list = [item.strip() for item in providers.split(",") if item.strip()]
    result = BenchmarkService(db).run(
        owner_id=current_user.id,
        test_name=test_name,
        mode=mode,
        prompt=prompt,
        providers=provider_list,
        context_json=context_json,
        knowledge_evidence_json=knowledge_evidence_json,
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        image_bytes=image_bytes,
        image_filename=image_filename,
        image_content_type=image_content_type,
        photo_id=photo_id,
    )
    return _to_response(result)


def _to_response(result: BenchmarkResult) -> BenchmarkRunResponse:
    return BenchmarkRunResponse(
        test_name=result.test_name,
        mode=result.mode.value,
        has_image=result.has_image,
        prompt_preview=result.prompt_preview,
        system_instruction=result.system_instruction,
        generation_settings=result.generation_settings,
        equivalence_notes=result.equivalence_notes,
        results=[_to_provider_read(item) for item in result.results],
        ran_at=result.ran_at,
    )


def _to_provider_read(item: ProviderResult) -> ProviderResultRead:
    return ProviderResultRead(
        provider=item.provider,
        model=item.model,
        status=item.status,
        started_at=item.started_at,
        ended_at=item.ended_at,
        latency_ms=item.latency_ms,
        response_text=item.response_text,
        error_code=item.error_code,
        error_message=item.error_message,
        usage=_to_usage(item.usage),
        estimated_cost_usd=item.estimated_cost_usd,
        generation_settings=item.generation_settings,
        metadata_notes=item.metadata_notes,
        raw_metadata=item.raw_metadata,
    )


def _to_usage(usage: TokenUsage) -> TokenUsageRead:
    return TokenUsageRead(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        reasoning_tokens=usage.reasoning_tokens,
        cached_input_tokens=usage.cached_input_tokens,
    )
