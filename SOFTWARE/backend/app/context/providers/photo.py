from __future__ import annotations

from sqlalchemy.orm import Session

from app.context.providers.base import ContextWarning, EngineQuery, ProviderResult, RankedItem, scope_id_for
from app.context.ranking import combine_score, match_scope, photo_type_relevance, temporal_relevance
from app.context.temporal import temporal_relation
from app.context.types import ContextScope, DataQualityStatus, SourceType, WarningType
from app.models.enums import AttachmentEntityType
from app.models.photo import Photo
from app.repositories.disease import DiseaseRepository
from app.repositories.photo import PhotoRepository
from app.schemas.context import ContextPhotoItem, ProvenanceRead


_ENTITY_SCOPE = {
    AttachmentEntityType.TREE: ContextScope.TREE,
    AttachmentEntityType.ROW: ContextScope.ROW,
    AttachmentEntityType.PARCEL: ContextScope.PARCEL,
    AttachmentEntityType.FARM: ContextScope.FARM,
    AttachmentEntityType.ACTIVITY: ContextScope.PARCEL,
    AttachmentEntityType.DISEASE_CASE: ContextScope.PARCEL,
    AttachmentEntityType.OBSERVATION: ContextScope.PARCEL,
}


class PhotoContextProvider:
    def __init__(self, db: Session) -> None:
        self.photos = PhotoRepository(db)
        self.diseases = DiseaseRepository(db)

    def get_source_type(self) -> str:
        return "photos"

    def supports(self, query: EngineQuery) -> bool:
        return query.profile.include_photos and query.subject.parcel is not None

    def collect(self, query: EngineQuery) -> ProviderResult:
        parcel = query.subject.parcel
        assert parcel is not None
        pairs: list[tuple[AttachmentEntityType, object]] = [(AttachmentEntityType.PARCEL, parcel.id)]
        if query.subject.row is not None:
            pairs.append((AttachmentEntityType.ROW, query.subject.row.id))
        if query.subject.tree is not None:
            pairs.append((AttachmentEntityType.TREE, query.subject.tree.id))
        if query.subject.activity is not None:
            pairs.append((AttachmentEntityType.ACTIVITY, query.subject.activity.id))
        cases = self.diseases.list_for_owner(query.owner_id, parcel_id=parcel.id)
        for case in cases:
            pairs.append((AttachmentEntityType.DISEASE_CASE, case.id))
            for observation in case.observations:
                pairs.append((AttachmentEntityType.OBSERVATION, observation.id))
        photos = self.photos.list_for_entities(
            [(entity_type, entity_id) for entity_type, entity_id in pairs],
            farm_id=parcel.farm_id,
        )
        current_id = query.request.photo_id or (query.subject.photo.id if query.subject.photo else None)
        if current_id is not None and all(photo.id != current_id for photo in photos):
            current = query.subject.photo or self.photos.get_for_owner(current_id, query.owner_id)
            if current is not None:
                photos = [current, *photos]
        case_by_id = {case.id: case for case in cases}
        items: list[RankedItem] = []
        seen: set[str] = set()
        for photo in photos:
            if str(photo.id) in seen:
                continue
            seen.add(str(photo.id))
            items.append(_rank_photo(photo, query, current_id, case_by_id))
        items.sort(key=lambda item: (-item.relevance_score, str(item.date or "")))
        warnings = []
        status = DataQualityStatus.AVAILABLE if items else DataQualityStatus.MISSING
        if not items:
            warnings.append(ContextWarning(WarningType.MISSING_DATA, "photos", "Nema fotografija za izabrani predmet."))
        return ProviderResult(
            source="photos",
            source_type=SourceType.USER_RECORD.value,
            status=status,
            items=items,
            collected=len(photos),
            warnings=warnings,
        )


def _rank_photo(photo: Photo, query: EngineQuery, current_id, case_by_id) -> RankedItem:
    parcel = query.subject.parcel
    tree_id = query.subject.tree.id if query.subject.tree else None
    row_id = query.subject.row.id if query.subject.row else None
    item_tree_id = photo.entity_id if photo.entity_type == AttachmentEntityType.TREE else None
    item_row_id = photo.entity_id if photo.entity_type == AttachmentEntityType.ROW else None
    item_parcel_id = photo.entity_id if photo.entity_type == AttachmentEntityType.PARCEL else (parcel.id if parcel else None)
    if photo.entity_type == AttachmentEntityType.DISEASE_CASE:
        case = case_by_id.get(photo.entity_id)
        if case is not None:
            item_tree_id = case.tree_id
            item_row_id = case.row_id
            item_parcel_id = case.parcel_id
    recorded = _ENTITY_SCOPE.get(photo.entity_type, ContextScope.PARCEL)
    matched, scope_score, scope_reason = match_scope(
        subject_tree_id=tree_id,
        subject_row_id=row_id,
        subject_parcel_id=parcel.id if parcel else None,
        item_tree_id=item_tree_id,
        item_row_id=item_row_id,
        item_parcel_id=item_parcel_id,
        recorded_scope=recorded,
    )
    photo_date = photo.taken_at.date() if photo.taken_at else photo.created_at.date()
    time_score, time_reason = temporal_relevance(photo_date, query.subject.event_date)
    is_current = current_id is not None and photo.id == current_id
    type_score, type_reason = photo_type_relevance(is_current=is_current, entity_type=photo.entity_type.value)
    score = 1.0 if is_current else combine_score(query.profile.request_type, scope_score, time_score, type_score)
    relation = temporal_relation(photo_date, query.subject.event_date)
    scope = matched.value if is_current and query.subject.tree else recorded.value
    if is_current and query.subject.tree:
        scope = ContextScope.TREE.value
    scope_id = scope_id_for(
        scope,
        farm_id=photo.farm_id,
        parcel_id=parcel.id if parcel else None,
        row_id=row_id if scope in {"ROW", "TREE"} else None,
        tree_id=tree_id if scope == "TREE" else item_tree_id,
    )
    provenance = ProvenanceRead(
        source="photo",
        source_id=str(photo.id),
        source_type=SourceType.USER_RECORD.value,
        scope=scope,
        scope_id=scope_id,
        recorded_at=photo.taken_at or photo.created_at,
        retrieved_at=query.retrieved_at,
        relevance_score=score,
    )
    payload = ContextPhotoItem(
        id=photo.id,
        date=photo.taken_at or photo.created_at,
        scope=scope,
        parcel_id=parcel.id if parcel else None,
        row_id=row_id if photo.entity_type in {AttachmentEntityType.ROW, AttachmentEntityType.TREE} else item_row_id,
        tree_id=item_tree_id if photo.entity_type == AttachmentEntityType.TREE else (tree_id if is_current else None),
        entity_type=photo.entity_type.value,
        entity_id=photo.entity_id,
        category=photo.entity_type.value,
        notes=photo.caption,
        original_filename=photo.original_filename,
        content_type=photo.content_type,
        storage_key=photo.storage_key,
        url=f"/photos/{photo.id}/file",
        is_current=is_current,
        temporal_relation=relation,
        relevance_score=score,
        provenance=provenance,
    )
    reasons = [scope_reason, time_reason, type_reason]
    if is_current:
        reasons.insert(0, "current photo")
    return RankedItem(
        kind="photo",
        id=str(photo.id),
        payload=payload,
        relevance_score=score,
        reasons=reasons,
        scope=scope,
        date=photo.taken_at or photo.created_at,
        temporal_relation=relation.value,
    )
