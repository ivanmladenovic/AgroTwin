from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai import get_ai_provider
from app.knowledge.taxonomy import (
    MANUALS,
    QueryRoute,
    classify_query,
    fold,
)
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.knowledge import KnowledgeAsset, KnowledgeChunk
from app.schemas.knowledge import EvidencePackage, EvidenceSource, RetrievalDebug

SEMANTIC_WEIGHT = 0.40
KEYWORD_WEIGHT = 0.35
METADATA_WEIGHT = 0.15
SECTION_WEIGHT = 0.10
MIN_CONFIDENCE = 0.18
LEVEL1_CONFIDENCE = 0.32
MAX_EVIDENCE = 8


@dataclass
class ScoredChunk:
    chunk: KnowledgeChunk
    document: Document
    semantic: float
    keyword: float
    metadata: float
    section: float
    score: float


def retrieve_evidence(
    db: Session,
    farm_id: UUID,
    question: str,
    *,
    agriser_only: bool = True,
    include_images: bool = False,
) -> EvidencePackage:
    route = classify_query(question)
    debug = RetrievalDebug(
        query=question,
        detected_domain=route.domains[0] if route.domains else None,
        detected_topic=route.topics[0] if route.topics else None,
        searched_documents=[],
        searched_sections=list(route.sections),
        retrieved_chunks=0,
        selected_chunks=0,
        retrieved_images=0,
        confidence=0.0,
        level=0,
    )
    if route.out_of_scope:
        return EvidencePackage(
            query=question,
            sufficient_evidence=False,
            out_of_scope=True,
            confidence=0.0,
            sources=[],
            images=[],
            tables=[],
            formulas=[],
            debug=debug,
        )
    if route.commercial:
        return EvidencePackage(
            query=question,
            sufficient_evidence=False,
            commercial=True,
            confidence=0.0,
            sources=[],
            images=[],
            tables=[],
            formulas=[],
            debug=debug,
        )

    provider = get_ai_provider()
    vector = provider.generate_embedding(question) if question.strip() else []
    documents = _candidate_documents(db, farm_id, route, agriser_only=agriser_only)
    if not documents:
        return EvidencePackage(query=question, sufficient_evidence=False, confidence=0.0, debug=debug)

    levels = _escalation_filters(route, documents)
    chosen: list[ScoredChunk] = []
    for level, allowed in enumerate(levels, start=1):
        debug.level = level
        debug.searched_documents = sorted({item.title for item in allowed})
        pool = _score_pool(db, farm_id, allowed, route, vector, include_images=include_images)
        debug.retrieved_chunks = len(pool)
        if not pool:
            continue
        top = pool[0].score
        multi_document = len(route.document_keys) > 1
        if level == 1 and multi_document:
            chosen = pool
            continue
        if level == 1 and top >= LEVEL1_CONFIDENCE:
            chosen = pool
            break
        if top >= MIN_CONFIDENCE:
            chosen = pool
            break
        chosen = pool
    if not chosen:
        return EvidencePackage(query=question, sufficient_evidence=False, confidence=0.0, debug=debug)

    selected = _diversify(chosen, route)[:MAX_EVIDENCE]
    confidence = round(selected[0].score, 4)
    debug.selected_chunks = len(selected)
    debug.confidence = confidence
    sources: list[EvidenceSource] = []
    tables: list[EvidenceSource] = []
    formulas: list[EvidenceSource] = []
    images: list[EvidenceSource] = []
    for item in selected:
        source = _to_source(item)
        if item.chunk.content_type == "table":
            tables.append(source)
        elif item.chunk.content_type == "formula":
            formulas.append(source)
        elif item.chunk.content_type == "image":
            images.append(source)
        else:
            sources.append(source)
    if include_images:
        extra_images = _related_images(db, [item.document.id for item in selected], route)
        debug.retrieved_images = len(extra_images)
        images.extend(extra_images[:4])
    sufficient = confidence >= MIN_CONFIDENCE and bool(sources or tables or formulas)
    return EvidencePackage(
        query=question,
        sufficient_evidence=sufficient,
        confidence=confidence,
        sources=sources,
        images=images,
        tables=tables,
        formulas=formulas,
        debug=debug,
    )


def _candidate_documents(db: Session, farm_id: UUID, route: QueryRoute, *, agriser_only: bool) -> list[Document]:
    stmt = select(Document).where(Document.farm_id == farm_id, Document.status == DocumentStatus.READY)
    docs = list(db.scalars(stmt).all())
    if agriser_only:
        agriser = [item for item in docs if item.source_kind == "agriser_manual"]
        if agriser:
            return agriser
        return []
    return docs


def _escalation_filters(route: QueryRoute, documents: list[Document]) -> list[list[Document]]:
    keyed = []
    for document in documents:
        key = _document_key(document)
        keyed.append((key, document))
    wanted = route.document_keys or [item.key for item in MANUALS]
    level1 = [doc for key, doc in keyed if key in wanted[:1] or (wanted and key == wanted[0])]
    if not level1 and wanted:
        level1 = [doc for key, doc in keyed if key in wanted]
    level2 = [doc for key, doc in keyed if key in wanted]
    level3 = [doc for _, doc in keyed]
    sequence = []
    for group in (level1, level2, level3):
        if group and group not in sequence:
            sequence.append(group)
    return sequence or [documents]


def _diversify(pool: list[ScoredChunk], route: QueryRoute) -> list[ScoredChunk]:
    if len(route.document_keys) <= 1 or len(pool) <= 2:
        return pool
    buckets: dict[str, list[ScoredChunk]] = {}
    for item in pool:
        buckets.setdefault(_document_key(item.document) or "other", []).append(item)
    mixed: list[ScoredChunk] = []
    while len(mixed) < MAX_EVIDENCE and any(buckets.values()):
        for key in route.document_keys + ["other"]:
            if buckets.get(key):
                mixed.append(buckets[key].pop(0))
            if len(mixed) >= MAX_EVIDENCE:
                break
    return mixed or pool


def _document_key(document: Document) -> str | None:
    blob = fold(f"{document.original_filename} {document.title}")
    for manual in MANUALS:
        if any(fold(token) in blob for token in manual.filename_contains):
            return manual.key
    extra = document.extra_metadata or {}
    domain = extra.get("domain")
    if domain in {"nutrition", "cultivation", "plant_protection"}:
        return "protection" if domain == "plant_protection" else domain
    return None


def _score_pool(
    db: Session,
    farm_id: UUID,
    documents: list[Document],
    route: QueryRoute,
    vector: list[float],
    *,
    include_images: bool,
) -> list[ScoredChunk]:
    ids = [item.id for item in documents]
    if not ids:
        return []
    stmt = select(KnowledgeChunk).where(KnowledgeChunk.farm_id == farm_id, KnowledgeChunk.document_id.in_(ids))
    if not include_images:
        stmt = stmt.where(KnowledgeChunk.content_type != "image")
    chunks = list(db.scalars(stmt).all())
    keyword_hits = _keyword_ids(db, farm_id, ids, route)
    docs = {item.id: item for item in documents}
    scored: list[ScoredChunk] = []
    for chunk in chunks:
        document = docs.get(chunk.document_id)
        if document is None:
            continue
        semantic = _cosine(vector, chunk.embedding or []) if vector and chunk.embedding else 0.0
        keyword = keyword_hits.get(chunk.id, _keyword_overlap(route, chunk))
        metadata = _metadata_score(route, document, chunk)
        section = _section_score(route, chunk)
        score = (
            semantic * SEMANTIC_WEIGHT
            + keyword * KEYWORD_WEIGHT
            + metadata * METADATA_WEIGHT
            + section * SECTION_WEIGHT
        )
        scored.append(
            ScoredChunk(
                chunk=chunk,
                document=document,
                semantic=semantic,
                keyword=keyword,
                metadata=metadata,
                section=section,
                score=score,
            )
        )
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored


def _keyword_ids(db: Session, farm_id: UUID, document_ids: list[UUID], route: QueryRoute) -> dict[UUID, float]:
    terms = [term for term in route.keywords if len(term) > 3][:8]
    if not terms:
        return {}
    query = " | ".join(re.sub(r"[^a-z0-9]+", " ", term) for term in terms)
    query = re.sub(r"\s+", " ", query).strip()
    if not query:
        return {}
    try:
        rows = db.execute(
            text(
                """
                SELECT id, ts_rank(to_tsvector('simple', coalesce(content, '')), plainto_tsquery('simple', :q)) AS rank
                FROM knowledge_chunks
                WHERE farm_id = CAST(:farm_id AS uuid)
                  AND document_id = ANY(CAST(:ids AS uuid[]))
                  AND to_tsvector('simple', coalesce(content, '')) @@ plainto_tsquery('simple', :q)
                """
            ),
            {"q": " ".join(terms), "farm_id": str(farm_id), "ids": [str(item) for item in document_ids]},
        ).all()
    except Exception:
        db.rollback()
        return {}
    ranked = {row[0]: float(row[1] or 0) for row in rows}
    if ranked:
        peak = max(ranked.values()) or 1.0
        return {key: value / peak for key, value in ranked.items()}
    return {}


def _keyword_overlap(route: QueryRoute, chunk: KnowledgeChunk) -> float:
    hay = fold((chunk.content or "") + " " + (chunk.section_title or "") + " " + (chunk.chapter or ""))
    terms = [term for term in route.keywords if 3 < len(term) < 80]
    if not terms:
        return 0.0
    hits = 0
    for term in terms:
        if len(term) <= 4:
            if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", hay):
                hits += 1
        elif term in hay:
            hits += 1
    return min(1.0, hits / max(2, min(len(terms), 6)))


def _metadata_score(route: QueryRoute, document: Document, chunk: KnowledgeChunk) -> float:
    score = 0.0
    key = _document_key(document)
    if key and key in route.document_keys:
        score += 0.7
    if chunk.domain and chunk.domain in route.domains:
        score += 0.25
    if chunk.topic and chunk.topic in route.topics:
        score += 0.35
    return min(1.0, score)


def _section_score(route: QueryRoute, chunk: KnowledgeChunk) -> float:
    blob = fold(f"{chunk.chapter or ''} {chunk.section_title or ''} {chunk.subsection or ''}")
    if not route.sections:
        return 0.0
    hits = sum(1 for section in route.sections if fold(section) in blob)
    return 1.0 if hits else 0.0


def _related_images(db: Session, document_ids: list[UUID], route: QueryRoute) -> list[EvidenceSource]:
    if not document_ids:
        return []
    stmt = select(KnowledgeAsset).where(KnowledgeAsset.document_id.in_(document_ids))
    assets = list(db.scalars(stmt).all())
    results: list[EvidenceSource] = []
    needles = [fold(section) for section in route.sections] + [fold(topic) for topic in route.topics]
    for asset in assets:
        blob = fold(f"{asset.section or ''} {asset.caption or ''} {asset.context or ''}")
        if needles and not any(needle and needle in blob for needle in needles):
            continue
        document = db.get(Document, asset.document_id)
        if document is None:
            continue
        results.append(
            EvidenceSource(
                document_id=document.id,
                document_title=document.title,
                pages=[asset.page_number],
                section=asset.section,
                chapter=asset.chapter,
                content_type="image",
                content=(asset.context or asset.caption or "")[:500],
                asset_id=asset.id,
                storage_key=asset.storage_key,
                score=0.5,
            )
        )
    return results[:6]


def _to_source(item: ScoredChunk) -> EvidenceSource:
    start = item.chunk.page_number
    end = item.chunk.page_end or start
    pages = [number for number in range(start or 0, (end or start or 0) + 1) if number]
    return EvidenceSource(
        chunk_id=item.chunk.id,
        document_id=item.document.id,
        document_title=item.document.title,
        pages=pages,
        section=item.chunk.section_title,
        chapter=item.chunk.chapter,
        content_type=item.chunk.content_type,
        content=item.chunk.content,
        score=round(item.score, 4),
    )


def _cosine(left: list[float], right: list[float]) -> float:
    length = min(len(left), len(right))
    if length == 0:
        return 0.0
    dot = sum(left[index] * right[index] for index in range(length))
    n1 = math.sqrt(sum(value * value for value in left[:length])) or 1.0
    n2 = math.sqrt(sum(value * value for value in right[:length])) or 1.0
    return dot / (n1 * n2)
