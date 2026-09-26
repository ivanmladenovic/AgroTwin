from __future__ import annotations

from sqlalchemy.orm import Session

from app.context.providers.base import ContextWarning, EngineQuery, ProviderResult
from app.context.types import DataQualityStatus, SourceType, WarningType
from app.context.weather_agg import aggregate_weather, parse_weather_days
from app.repositories.weather import WeatherCacheRepository
from app.schemas.context import ContextWeatherDay, ContextWeatherRead


class WeatherContextProvider:
    def __init__(self, db: Session) -> None:
        self.cache = WeatherCacheRepository(db)

    def get_source_type(self) -> str:
        return "weather"

    def supports(self, query: EngineQuery) -> bool:
        return query.profile.include_weather and query.subject.parcel is not None

    def collect(self, query: EngineQuery) -> ProviderResult:
        parcel = query.subject.parcel
        assert parcel is not None
        warnings: list[ContextWarning] = []
        cache = self.cache.get_for_parcel(parcel.id)
        if cache is None:
            warnings.append(
                ContextWarning(
                    WarningType.MISSING_DATA,
                    "weather",
                    "Nema keširanih vremenskih podataka za izabrani period.",
                )
            )
            payload = ContextWeatherRead(
                status=DataQualityStatus.MISSING,
                message="Nema keširanih vremenskih podataka za izabrani period.",
            )
            return ProviderResult(
                source="weather",
                source_type=SourceType.EXTERNAL_WEATHER_DATA.value,
                status=DataQualityStatus.MISSING,
                payload=payload,
                warnings=warnings,
            )

        normalized = cache.normalized_response if isinstance(cache.normalized_response, dict) else {}
        days = parse_weather_days(normalized.get("forecast") if isinstance(normalized.get("forecast"), list) else [])
        wanted = query.profile.weather_days
        days = days[: query.profile.budget.max_weather_records]
        aggregates = aggregate_weather(days)
        stale = cache.forecast_date != query.subject.event_date
        status = DataQualityStatus.STALE if stale else DataQualityStatus.AVAILABLE
        if wanted > len(days):
            status = DataQualityStatus.PARTIAL if days else DataQualityStatus.MISSING
            warnings.append(
                ContextWarning(
                    WarningType.LIMITED_HISTORY,
                    "weather",
                    "AgroTwin čuva keš prognoze (Yr / MET Norway), ne istorijsku seriju. "
                    f"Dostupno je {len(days)} dana umesto traženih {wanted}.",
                )
            )
        if stale:
            warnings.append(
                ContextWarning(
                    WarningType.STALE_DATA,
                    "weather",
                    "Keš prognoze nije od datuma događaja. Prikazani su poslednji dostupni podaci.",
                )
            )
        payload = ContextWeatherRead(
            status=status,
            is_stale=stale,
            fetched_at=cache.fetched_at,
            period_start=aggregates.period_start,
            period_end=aggregates.period_end,
            minimum_temperature=aggregates.minimum_temperature,
            maximum_temperature=aggregates.maximum_temperature,
            average_temperature=aggregates.average_temperature,
            precipitation=aggregates.precipitation,
            rainy_days=aggregates.rainy_days,
            hot_days=aggregates.hot_days,
            frost_days=aggregates.frost_days,
            days=[
                ContextWeatherDay(
                    date=day.date,
                    min_temperature=day.min_temperature,
                    max_temperature=day.max_temperature,
                    precipitation=day.precipitation,
                )
                for day in days
            ],
            message=warnings[0].message if warnings else None,
        )
        return ProviderResult(
            source="weather",
            source_type=SourceType.EXTERNAL_WEATHER_DATA.value,
            status=status,
            payload=payload,
            collected=len(days),
            warnings=warnings,
        )
