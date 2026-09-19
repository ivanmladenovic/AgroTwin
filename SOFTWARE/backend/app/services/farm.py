from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.farm import Farm
from app.repositories.farm import FarmRepository


class FarmService:
    def __init__(self, db: Session) -> None:
        self.farms = FarmRepository(db)

    def list_for_user(self, owner_id: UUID) -> list[Farm]:
        return self.farms.list_by_owner(owner_id)

    def get_for_user(self, farm_id: UUID, owner_id: UUID) -> Farm:
        farm = self.farms.get_by_id_for_owner(farm_id, owner_id)
        if farm is None:
            raise NotFoundError("Gazdinstvo nije pronađeno")
        return farm
