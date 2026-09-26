from __future__ import annotations

from app.benchmark.types import BenchmarkMode

PRESET_TEST_CASES: list[dict] = [
    {
        "id": "general_reasoning",
        "name": "TEST 1 — General agricultural reasoning",
        "mode": BenchmarkMode.TEXT.value,
        "prompt": (
            "Explain in plain language how soil moisture and recent rainfall "
            "can influence hazelnut orchard management decisions in early autumn. "
            "Stay general; do not invent a diagnosis for a specific orchard."
        ),
        "context": None,
        "knowledge_evidence": None,
    },
    {
        "id": "image_observation",
        "name": "TEST 2 — Image observation",
        "mode": BenchmarkMode.IMAGE.value,
        "prompt": (
            "Describe only what you can observe in the attached orchard photo. "
            "Separate visible observations from any uncertain interpretations. "
            "Do not invent a disease name if you cannot see clear evidence."
        ),
        "context": None,
        "knowledge_evidence": None,
    },
    {
        "id": "image_context",
        "name": "TEST 3 — Image + AgroTwin context",
        "mode": BenchmarkMode.IMAGE_CONTEXT.value,
        "prompt": (
            "Using the attached photo and the supplied AgroTwin context, list "
            "observations and possible next inspection steps. Do not invent treatments."
        ),
        "context": {
            "parcel": {"name": "Test Parcel", "crop": "Hazelnut"},
            "row": {"number": 12},
            "tree": {"number": 37},
            "recent_activities": [
                {"date": "2026-09-05", "type": "fertilization"},
                {"date": "2026-09-08", "type": "irrigation"},
            ],
            "weather": {
                "recent_temperature": "daytime highs around 24 C",
                "recent_precipitation": "12 mm over the last 7 days",
            },
            "soil": {"ph": 6.8, "source_type": "modeled_estimate"},
        },
        "knowledge_evidence": None,
    },
    {
        "id": "context_evidence",
        "name": "TEST 4 — Context + Agriser evidence",
        "mode": BenchmarkMode.FULL.value,
        "prompt": (
            "Based only on the supplied AgroTwin context and knowledge evidence, "
            "summarize what is known and what remains unknown. Do not invent facts "
            "that are not in the evidence."
        ),
        "context": {
            "parcel": {"name": "Test Parcel", "crop": "Hazelnut"},
            "row": {"number": 4},
            "tree": {"number": 9},
            "recent_activities": [{"date": "2026-08-20", "type": "pruning"}],
            "weather": {"recent_temperature": "mild", "recent_precipitation": "dry spell"},
            "soil": {"ph": 6.2, "source_type": "modeled_estimate"},
        },
        "knowledge_evidence": [
            {
                "source": "Priručnik - Ishrana leske",
                "page": 12,
                "section": "Mikroelementi",
                "content": (
                    "Nedostatak bora može uticati na zametanje ploda. "
                    "Preporuke za intervenciju treba zasnivati na laboratorijskoj analizi "
                    "i lokalnim uslovima, ne na nagađanju."
                ),
            }
        ],
    },
    {
        "id": "insufficient_evidence",
        "name": "TEST 5 — Insufficient evidence / should say it does not know",
        "mode": BenchmarkMode.TEXT.value,
        "prompt": (
            "Based only on the supplied evidence, what can you conclude about the "
            "health status of tree 37? If evidence is insufficient, say so explicitly."
        ),
        "context": {
            "parcel": {"name": "Test Parcel", "crop": "Hazelnut"},
            "tree": {"number": 37},
        },
        "knowledge_evidence": [
            {
                "source": "Incomplete field note",
                "page": None,
                "section": "Observation",
                "content": "Producer reported 'something looks off' without photos or lab results.",
            }
        ],
    },
]
