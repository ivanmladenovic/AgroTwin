from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


WeatherStatus = Literal["ok", "stale", "no_location", "invalid_location", "unavailable"]


class DailyForecastRead(BaseModel):
    date: date
    min_temperature: float | None = None
    max_temperature: float | None = None
    precipitation: float = 0
    precipitation_probability: int | None = None
    symbol_code: str | None = None


class ParcelWeatherRead(BaseModel):
    available: bool
    status: WeatherStatus
    message: str | None = None
    parcel_id: UUID
    parcel_name: str
    latitude: float | None = None
    longitude: float | None = None
    timezone: str
    forecast: list[DailyForecastRead] = Field(default_factory=list)
    fetched_at: datetime | None = None
    source: str = "Yr"
