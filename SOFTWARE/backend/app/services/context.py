from uuid import UUID

from sqlalchemy.orm import Session

from app.context.engine import ContextEngine
from app.context.request import ContextRequest
from app.schemas.context import AgroTwinContext, ContextBuildRequest


class ContextService:
    def __init__(self, db: Session) -> None:
        self.engine = ContextEngine(db)

    def build(self, owner_id: UUID, payload: ContextBuildRequest) -> AgroTwinContext:
        request = ContextRequest(
            request_type=payload.request_type,
            parcel_id=payload.parcel_id,
            row_id=payload.row_id,
            tree_id=payload.tree_id,
            photo_id=payload.photo_id,
            activity_id=payload.activity_id,
            disease_case_id=payload.disease_case_id,
            season_year=payload.season_year,
            event_date=payload.event_date,
            query=payload.query,
            include_debug=payload.include_debug,
        )
        return self.engine.build_context(owner_id, request)
