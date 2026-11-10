"""Local equirectangular metric projection around a parcel origin (Serbia-scale parcels)."""

from __future__ import annotations

import math
from dataclasses import dataclass


METERS_PER_DEGREE_LAT = 111_320.0


@dataclass(frozen=True)
class LocalMetricProjection:
    origin_lon: float
    origin_lat: float

    @classmethod
    def from_lonlat(cls, lon: float, lat: float) -> LocalMetricProjection:
        return cls(origin_lon=float(lon), origin_lat=float(lat))

    @property
    def meters_per_deg_lon(self) -> float:
        return METERS_PER_DEGREE_LAT * max(math.cos(math.radians(self.origin_lat)), 0.2)

    def to_xy(self, lon: float, lat: float) -> tuple[float, float]:
        x = (float(lon) - self.origin_lon) * self.meters_per_deg_lon
        y = (float(lat) - self.origin_lat) * METERS_PER_DEGREE_LAT
        return x, y

    def to_lonlat(self, x: float, y: float) -> tuple[float, float]:
        lon = self.origin_lon + float(x) / self.meters_per_deg_lon
        lat = self.origin_lat + float(y) / METERS_PER_DEGREE_LAT
        return lon, lat
