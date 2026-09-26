from __future__ import annotations

import json
from typing import Any

from app.benchmark.types import BenchmarkMode


def build_user_message(
    *,
    prompt: str,
    mode: BenchmarkMode,
    context: dict[str, Any] | list[Any] | None,
    knowledge_evidence: list[Any] | dict[str, Any] | None,
    has_image: bool,
) -> str:
    """Assemble the same plain-text user payload for every provider.

    Context and knowledge evidence are included whenever the caller supplied them.
    Mode mainly controls whether an image is required; it does not rewrite the prompt.
    """
    del mode  # reserved for future mode-specific assembly without prompt mutation
    sections: list[str] = [prompt.strip()]
    if context is not None:
        sections.append("AgroTwin Context (test data):\n" + _pretty(context))
    if knowledge_evidence is not None:
        sections.append("Knowledge evidence (test data):\n" + _pretty(knowledge_evidence))
    if has_image:
        sections.append(
            "An image is attached to this request. Describe only what you can observe "
            "in the image together with the supplied text."
        )
    return "\n\n".join(part for part in sections if part)


def mode_requires_image(mode: BenchmarkMode) -> bool:
    return mode in {BenchmarkMode.IMAGE, BenchmarkMode.IMAGE_CONTEXT}


def _pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)
