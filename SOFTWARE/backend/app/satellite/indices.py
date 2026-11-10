"""Vegetation / water-stress index formulas for Sentinel-2.

Formulas are named and configurable via Settings. Do not mix unnamed variants.

NDVI (Rouse et al.):
  (NIR - RED) / (NIR + RED)
  Sentinel-2: NIR = B08, RED = B04

NDRE (Red-Edge NDVI):
  (NIR_narrow - RedEdge) / (NIR_narrow + RedEdge)
  Sentinel-2 default: NIR_narrow = B8A, RedEdge = B05
  B8A is preferred over B08 for red-edge contrast at 20 m.

NDWI_GAO (Gao 1996 — canopy water content / vegetation water stress):
  (NIR - SWIR) / (NIR + SWIR)
  Sentinel-2: NIR = B08, SWIR = B11
  This is NOT McFeeters NDWI ((Green-NIR)/(Green+NIR)), which detects open water.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Callable


class IndexName(str, Enum):
    NDVI = "ndvi"
    NDRE = "ndre"
    NDWI = "ndwi"  # NDWI_GAO formulation


INDEX_FORMULAS: dict[str, str] = {
    IndexName.NDVI.value: "(B08 - B04) / (B08 + B04)",
    IndexName.NDRE.value: "(B8A - B05) / (B8A + B05)",
    IndexName.NDWI.value: "(B08 - B11) / (B08 + B11)  # NDWI_GAO",
}

# Native Sentinel-2 L2A band resolutions for the bands used in each index.
# Display/rendering resolution is configured separately and must not be presented as native.
INDEX_NATIVE_RESOLUTION: dict[str, str] = {
    IndexName.NDVI.value: "10 m (B04, B08)",
    IndexName.NDRE.value: "20 m (B05, B8A)",
    IndexName.NDWI.value: "10–20 m (B08 10 m, B11 20 m)",
}

# Visualization upsample only — must never be labeled as native Sentinel resolution.
DISPLAY_RESOLUTION_M = 2.5


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0.0:
        return None
    return numerator / denominator


def ndvi(nir: float, red: float) -> float | None:
    return _safe_ratio(nir - red, nir + red)


def ndre(nir_narrow: float, red_edge: float) -> float | None:
    return _safe_ratio(nir_narrow - red_edge, nir_narrow + red_edge)


def ndwi_gao(nir: float, swir: float) -> float | None:
    """Gao (1996) NDWI — vegetation water content, not McFeeters open-water NDWI."""
    return _safe_ratio(nir - swir, nir + swir)


def decimal_or_none(value: float | None, places: str = "0.0001") -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal(places))


IndexCalculator = Callable[[float, float], float | None]

CALCULATORS: dict[IndexName, IndexCalculator] = {
    IndexName.NDVI: ndvi,
    IndexName.NDRE: ndre,
    IndexName.NDWI: ndwi_gao,
}
