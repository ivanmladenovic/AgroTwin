from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.catalog import CatalogItemRead
from app.schemas.common import IDSchema


class OrchardSeasonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    starts_on: date
    ends_on: date
    parcel_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_range(self) -> "OrchardSeasonCreate":
        if self.ends_on < self.starts_on:
            raise ValueError("Kraj sezone ne može biti pre početka.")
        return self


class OrchardSeasonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    starts_on: date | None = None
    ends_on: date | None = None
    parcel_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class OrchardSeasonRead(IDSchema):
    farm_id: UUID
    parcel_id: UUID | None
    parcel_name: str | None = None
    name: str
    starts_on: date
    ends_on: date
    notes: str | None
    created_by_id: UUID | None


class TaskScheduleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    activity_type_id: UUID
    weekdays: list[int] = Field(min_length=1)
    starts_on: date | None = None
    ends_on: date | None = None
    season_id: UUID | None = None
    parcel_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool = True
    # When true and no season/dates: use calendar year of starts_on or today
    whole_year: bool = False
    year: int | None = Field(default=None, ge=1990, le=2100)

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int]) -> list[int]:
        cleaned = sorted({int(day) for day in value})
        if not cleaned or any(day < 0 or day > 6 for day in cleaned):
            raise ValueError("Dani u nedelji moraju biti 0–6 (ponedeljak–nedelja).")
        return cleaned

    @model_validator(mode="after")
    def validate_window(self) -> "TaskScheduleCreate":
        if self.season_id is None and not self.whole_year and (self.starts_on is None or self.ends_on is None):
            raise ValueError("Izaberite sezonu, celu godinu ili period od–do.")
        if self.starts_on is not None and self.ends_on is not None and self.ends_on < self.starts_on:
            raise ValueError("Kraj perioda ne može biti pre početka.")
        return self


class TaskScheduleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    activity_type_id: UUID | None = None
    weekdays: list[int] | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    season_id: UUID | None = None
    parcel_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        cleaned = sorted({int(day) for day in value})
        if not cleaned or any(day < 0 or day > 6 for day in cleaned):
            raise ValueError("Dani u nedelji moraju biti 0–6 (ponedeljak–nedelja).")
        return cleaned


class TaskScheduleRead(IDSchema):
    farm_id: UUID
    parcel_id: UUID | None
    parcel_name: str | None = None
    season_id: UUID | None
    season_name: str | None = None
    activity_type: CatalogItemRead
    title: str
    starts_on: date
    ends_on: date
    weekdays: list[int]
    notes: str | None
    is_active: bool
    created_by_id: UUID | None
    planned_count: int = 0
