from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.weather import ParcelWeatherRead
from app.services.weather import WeatherService

router = APIRouter(tags=["weather"])


@router.get("/parcels/{parcel_id}/weather", response_model=ParcelWeatherRead)
def get_parcel_weather(parcel_id: UUID, current_user: CurrentUser, db: DBSession) -> ParcelWeatherRead:
    return WeatherService(db).get_forecast(current_user.id, parcel_id)
