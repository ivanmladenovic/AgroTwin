from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.disease import DiseaseCase, DiseaseObservation
from app.models.enums import (
    AttachmentEntityType,
    DiseaseCaseStatus,
    DiseaseCategory,
    DiseaseSeverity,
    HealthStatus,
    TreeStatus,
)
from app.models.parcel import Parcel
from app.models.photo import Photo
from app.models.row import Row
from app.models.tree import Tree
from app.repositories.disease import DiseaseRepository, ObservationRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.photo import PhotoRepository
from app.repositories.row import RowRepository
from app.repositories.tree import TreeRepository
from app.schemas.disease import (
    DiseaseCaseCreate,
    DiseaseCaseDetailRead,
    DiseaseCaseRead,
    DiseaseCaseUpdate,
    ObservationCreate,
    ObservationRead,
    PhotoRead,
)
from app.storage import get_storage
from app.storage.images import compress_photo

ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
MAX_PHOTO_BYTES = 25 * 1024 * 1024


class DiseaseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.cases = DiseaseRepository(db)
        self.observations = ObservationRepository(db)
        self.photos = PhotoRepository(db)
        self.parcels = ParcelRepository(db)
        self.rows = RowRepository(db)
        self.trees = TreeRepository(db)
        self.storage = get_storage()

    def list_cases(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        row_id: UUID | None = None,
        tree_id: UUID | None = None,
        status: DiseaseCaseStatus | None = None,
        category: DiseaseCategory | None = None,
    ) -> list[DiseaseCaseRead]:
        records = self.cases.list_for_owner(
            owner_id,
            parcel_id=parcel_id,
            row_id=row_id,
            tree_id=tree_id,
            status=status,
            category=category,
        )
        return [self.to_case_read(item) for item in records]

    def get_case(self, case_id: UUID, owner_id: UUID) -> DiseaseCase:
        case = self.cases.get_for_owner(case_id, owner_id)
        if case is None:
            raise NotFoundError("Slučaj nije pronađen")
        return case

    def get_case_detail(self, case_id: UUID, owner_id: UUID) -> DiseaseCaseDetailRead:
        case = self.get_case(case_id, owner_id)
        observations = [
            self.to_observation_read(item) for item in self.observations.list_for_case(case.id)
        ]
        summary = self.to_case_read(case, observations=observations)
        photos = [photo for observation in observations for photo in observation.photos]
        photos.extend(self._photos_for(AttachmentEntityType.DISEASE_CASE, case.id))
        return DiseaseCaseDetailRead(**summary.model_dump(), observations=observations, photos=photos)

    def create_case(self, owner_id: UUID, payload: DiseaseCaseCreate, created_by_id: UUID) -> DiseaseCase:
        parcel, row_id, tree_id, extra_notes = self._resolve_scope(
            owner_id, payload.parcel_id, payload.row_id, payload.tree_id, payload.tree_ids
        )
        notes = payload.notes
        if extra_notes:
            notes = f"{notes.strip()}\n{extra_notes}".strip() if notes else extra_notes
        case = DiseaseCase(
            farm_id=parcel.farm_id,
            parcel_id=parcel.id,
            row_id=row_id,
            tree_id=tree_id,
            title=payload.title.strip(),
            description=payload.description,
            category=payload.category,
            severity=payload.severity,
            status=payload.status,
            detected_on=payload.detected_on,
            resolved_on=date.today() if payload.status == DiseaseCaseStatus.RESOLVED else None,
            notes=notes,
            created_by_id=created_by_id,
        )
        self.cases.add(case)
        self.db.flush()
        self.observations.add(
            DiseaseObservation(
                disease_case_id=case.id,
                observed_on=payload.detected_on,
                symptoms=payload.symptoms,
                notes=notes,
                created_by_id=created_by_id,
            )
        )
        if tree_id is not None:
            self.sync_tree_health(tree_id)
        self.db.commit()
        loaded = self.cases.get_for_owner(case.id, owner_id)
        assert loaded is not None
        return loaded

    def update_case(self, case_id: UUID, owner_id: UUID, payload: DiseaseCaseUpdate) -> DiseaseCase:
        case = self.get_case(case_id, owner_id)
        data = payload.model_dump(exclude_unset=True)
        if "title" in data and data["title"] is not None:
            data["title"] = data["title"].strip()
        if "status" in data:
            if data["status"] == DiseaseCaseStatus.RESOLVED and case.resolved_on is None:
                case.resolved_on = date.today()
            if data["status"] != DiseaseCaseStatus.RESOLVED:
                case.resolved_on = None
        for field, value in data.items():
            setattr(case, field, value)
        if case.tree_id is not None:
            self.sync_tree_health(case.tree_id)
        self.db.commit()
        return self.get_case(case.id, owner_id)

    def add_observation(
        self,
        case_id: UUID,
        owner_id: UUID,
        payload: ObservationCreate,
        created_by_id: UUID,
    ) -> DiseaseObservation:
        case = self.get_case(case_id, owner_id)
        observation = DiseaseObservation(
            disease_case_id=case.id,
            observed_on=payload.observed_on,
            symptoms=payload.symptoms,
            notes=payload.notes,
            created_by_id=created_by_id,
        )
        self.observations.add(observation)
        self.db.flush()
        observation_id = observation.id
        self.db.commit()
        loaded = self.observations.get(observation_id)
        assert loaded is not None
        return loaded

    def add_photo(
        self,
        owner_id: UUID,
        *,
        entity_type: AttachmentEntityType,
        entity_id: UUID,
        filename: str,
        content_type: str,
        content: bytes,
        caption: str | None,
        uploaded_by_id: UUID,
    ) -> Photo:
        content_type = (content_type or "").split(";")[0].strip().lower()
        if content_type == "image/jpg":
            content_type = "image/jpeg"
        if content_type not in ALLOWED_PHOTO_TYPES:
            raise AppError("Prihvataju se samo JPEG, PNG, WebP i GIF slike", status_code=422, code="invalid_photo")
        if len(content) > MAX_PHOTO_BYTES:
            raise AppError("Fotografija je veća od 25 MB", status_code=422, code="photo_too_large")
        farm_id = self._farm_for_entity(owner_id, entity_type, entity_id)
        compressed = compress_photo(content, filename)
        content = compressed.content
        content_type = compressed.content_type
        filename = compressed.filename
        key = f"photos/{farm_id}/{uuid4().hex}{compressed.extension}"
        self.storage.put(key, content, content_type)
        photo = Photo(
            farm_id=farm_id,
            entity_type=entity_type,
            entity_id=entity_id,
            storage_key=key,
            original_filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            caption=caption,
            uploaded_by_id=uploaded_by_id,
        )
        self.photos.add(photo)
        self.db.commit()
        self.db.refresh(photo)
        return photo

    def get_photo(self, photo_id: UUID, owner_id: UUID) -> Photo:
        from sqlalchemy import select

        from app.models.farm import Farm

        photo = self.photos.get(photo_id)
        if photo is None:
            raise NotFoundError("Fotografija nije pronađena")
        owned = self.db.scalar(select(Farm.id).where(Farm.id == photo.farm_id, Farm.owner_id == owner_id))
        if owned is None:
            raise NotFoundError("Fotografija nije pronađena")
        return photo

    def photo_bytes(self, photo: Photo) -> tuple[bytes, str]:
        return self.storage.get(photo.storage_key), photo.content_type

    def photo_local_path(self, photo: Photo):
        return self.storage.local_path(photo.storage_key)

    def sync_tree_health(self, tree_id: UUID) -> None:
        self.db.flush()
        tree = self.db.get(Tree, tree_id)
        if tree is None or tree.status == TreeStatus.REMOVED:
            return
        open_cases = self.cases.list_open_for_tree(tree.id)
        if not open_cases:
            tree.health_status = HealthStatus.HEALTHY
            return
        severities = {item.severity for item in open_cases}
        if DiseaseSeverity.CRITICAL in severities or DiseaseSeverity.HIGH in severities:
            tree.health_status = HealthStatus.ISSUE
        elif any(item.status == DiseaseCaseStatus.UNKNOWN for item in open_cases):
            tree.health_status = HealthStatus.UNKNOWN
        else:
            tree.health_status = HealthStatus.MONITORING

    def to_case_read(
        self,
        case: DiseaseCase,
        observations: list[ObservationRead] | None = None,
    ) -> DiseaseCaseRead:
        parcel = self.db.get(Parcel, case.parcel_id)
        row = self.db.get(Row, case.row_id) if case.row_id else None
        tree = self.db.get(Tree, case.tree_id) if case.tree_id else None
        observation_models = observations or [
            self.to_observation_read(item) for item in self.observations.list_for_case(case.id)
        ]
        photo_count = sum(len(item.photos) for item in observation_models)
        photo_count += len(self.photos.list_for_entity(AttachmentEntityType.DISEASE_CASE, case.id))
        return DiseaseCaseRead(
            id=case.id,
            created_at=case.created_at,
            updated_at=case.updated_at,
            farm_id=case.farm_id,
            parcel_id=case.parcel_id,
            row_id=case.row_id,
            tree_id=case.tree_id,
            title=case.title,
            description=case.description,
            category=case.category,
            severity=case.severity,
            status=case.status,
            detected_on=case.detected_on,
            resolved_on=case.resolved_on,
            notes=case.notes,
            created_by_id=case.created_by_id,
            parcel_name=parcel.name if parcel else None,
            row_number=row.row_number if row else None,
            tree_public_id=tree.public_id if tree else None,
            observation_count=len(observation_models),
            photo_count=photo_count,
        )

    def to_observation_read(self, observation: DiseaseObservation) -> ObservationRead:
        return ObservationRead(
            id=observation.id,
            created_at=observation.created_at,
            updated_at=observation.updated_at,
            disease_case_id=observation.disease_case_id,
            observed_on=observation.observed_on,
            symptoms=observation.symptoms,
            notes=observation.notes,
            created_by_id=observation.created_by_id,
            photos=self._photos_for(AttachmentEntityType.OBSERVATION, observation.id),
        )

    def to_photo_read(self, photo: Photo) -> PhotoRead:
        return PhotoRead(
            id=photo.id,
            created_at=photo.created_at,
            updated_at=photo.updated_at,
            farm_id=photo.farm_id,
            entity_type=photo.entity_type,
            entity_id=photo.entity_id,
            original_filename=photo.original_filename,
            content_type=photo.content_type,
            size_bytes=photo.size_bytes,
            caption=photo.caption,
            taken_at=photo.taken_at,
            uploaded_by_id=photo.uploaded_by_id,
            uploaded_at=photo.created_at,
            url=f"/photos/{photo.id}/file",
        )

    def tree_photos(self, tree_id: UUID, cases: list[DiseaseCase]) -> list[PhotoRead]:
        pairs: list[tuple[AttachmentEntityType, UUID]] = [(AttachmentEntityType.TREE, tree_id)]
        observation_ids: list[UUID] = []
        for case in cases:
            pairs.append((AttachmentEntityType.DISEASE_CASE, case.id))
            for observation in self.observations.list_for_case(case.id):
                observation_ids.append(observation.id)
                pairs.append((AttachmentEntityType.OBSERVATION, observation.id))
        photos = self.photos.list_for_entities(pairs)
        return [self.to_photo_read(item) for item in photos]

    def _photos_for(self, entity_type: AttachmentEntityType, entity_id: UUID) -> list[PhotoRead]:
        return [self.to_photo_read(item) for item in self.photos.list_for_entity(entity_type, entity_id)]

    def _resolve_scope(
        self,
        owner_id: UUID,
        parcel_id: UUID,
        row_id: UUID | None,
        tree_id: UUID | None,
        tree_ids: list[UUID] | None = None,
    ) -> tuple[Parcel, UUID | None, UUID | None, str | None]:
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        selected_ids = list(dict.fromkeys([*(tree_ids or []), *([tree_id] if tree_id else [])]))
        extra_notes = None
        resolved_row_id = row_id
        resolved_tree_id = tree_id
        if selected_ids:
            trees = []
            for item_id in selected_ids:
                found = self.trees.get_for_parcel(parcel.id, item_id)
                if found is None:
                    raise NotFoundError("Stablo nije pronađeno")
                tree, _row_number = found
                trees.append(tree)
            if len(trees) == 1:
                resolved_tree_id = trees[0].id
                resolved_row_id = trees[0].row_id
            else:
                resolved_tree_id = None
                row_ids = {item.row_id for item in trees}
                resolved_row_id = next(iter(row_ids)) if len(row_ids) == 1 else row_id
                extra_notes = "Zahvaćena stabla: " + ", ".join(item.public_id for item in trees)
        elif row_id is not None:
            row = self.rows.get_for_parcel(parcel.id, row_id)
            if row is None:
                raise NotFoundError("Red nije pronađen")
            resolved_row_id = row.id
            resolved_tree_id = None
        return parcel, resolved_row_id, resolved_tree_id, extra_notes

    def _farm_for_entity(self, owner_id: UUID, entity_type: AttachmentEntityType, entity_id: UUID) -> UUID:
        if entity_type == AttachmentEntityType.OBSERVATION:
            observation = self.observations.get(entity_id)
            if observation is None:
                raise NotFoundError("Opažanje nije pronađeno")
            case = self.get_case(observation.disease_case_id, owner_id)
            return case.farm_id
        if entity_type == AttachmentEntityType.DISEASE_CASE:
            return self.get_case(entity_id, owner_id).farm_id
        if entity_type == AttachmentEntityType.TREE:
            from sqlalchemy import select
            from app.models.farm import Farm

            stmt = (
                select(Tree)
                .join(Parcel, Tree.parcel_id == Parcel.id)
                .join(Farm, Parcel.farm_id == Farm.id)
                .where(Tree.id == entity_id, Farm.owner_id == owner_id)
            )
            tree = self.db.scalars(stmt).first()
            if tree is None:
                raise NotFoundError("Stablo nije pronađeno")
            parcel = self.db.get(Parcel, tree.parcel_id)
            assert parcel is not None
            return parcel.farm_id
        if entity_type == AttachmentEntityType.HARVEST_EVENT:
            from sqlalchemy import select
            from app.models.farm import Farm
            from app.models.harvest import HarvestEvent

            stmt = (
                select(HarvestEvent)
                .join(Farm, HarvestEvent.farm_id == Farm.id)
                .where(HarvestEvent.id == entity_id, Farm.owner_id == owner_id)
            )
            event = self.db.scalars(stmt).first()
            if event is None:
                raise NotFoundError("Berba nije pronađena")
            return event.farm_id
        raise AppError("Fotografije se mogu vezati samo za stablo, opažanje, slučaj ili berbu", status_code=422)
