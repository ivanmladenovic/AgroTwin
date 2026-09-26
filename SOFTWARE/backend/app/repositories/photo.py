from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.enums import AttachmentEntityType
from app.models.farm import Farm
from app.models.photo import Photo


class PhotoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_entity(self, entity_type: AttachmentEntityType, entity_id: UUID) -> list[Photo]:
        stmt = (
            select(Photo)
            .where(Photo.entity_type == entity_type, Photo.entity_id == entity_id)
            .order_by(Photo.taken_at.desc().nullslast(), Photo.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_for_entities(
        self,
        pairs: list[tuple[AttachmentEntityType, UUID]],
        *,
        farm_id: UUID | None = None,
    ) -> list[Photo]:
        if not pairs:
            return []
        conditions = [
            (Photo.entity_type == entity_type) & (Photo.entity_id == entity_id) for entity_type, entity_id in pairs
        ]
        stmt = select(Photo).where(or_(*conditions)).order_by(Photo.created_at.desc())
        if farm_id is not None:
            stmt = stmt.where(Photo.farm_id == farm_id)
        return list(self.db.scalars(stmt).all())

    def get(self, photo_id: UUID) -> Photo | None:
        return self.db.get(Photo, photo_id)

    def get_for_owner(self, photo_id: UUID, owner_id: UUID) -> Photo | None:
        stmt = (
            select(Photo)
            .join(Farm, Photo.farm_id == Farm.id)
            .where(Photo.id == photo_id, Farm.owner_id == owner_id)
        )
        return self.db.scalars(stmt).first()

    def add(self, photo: Photo) -> Photo:
        self.db.add(photo)
        return photo

    def delete(self, photo: Photo) -> None:
        self.db.delete(photo)
