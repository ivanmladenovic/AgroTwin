from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.weather import WeatherForecastCache


class WeatherCacheRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_parcel(self, parcel_id: UUID) -> WeatherForecastCache | None:
        stmt = select(WeatherForecastCache).where(WeatherForecastCache.parcel_id == parcel_id)
        return self.db.scalars(stmt).first()

    def add(self, cache: WeatherForecastCache) -> WeatherForecastCache:
        self.db.add(cache)
        return cache
