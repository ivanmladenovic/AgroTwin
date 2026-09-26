from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

PROVIDER_NAME = "SoilGrids"
SOURCE_TYPE = "modeled_estimate"
SOURCE_LABEL = "Modelovana procena – SoilGrids"
SOURCE_EXPLANATION = (
    "SoilGrids daje modelovane procene osobina zemljišta na osnovu prostornih podataka. "
    "Vrednosti ne predstavljaju laboratorijsku analizu konkretne parcele."
)
DATASET_VERSION = "2.0"
SPATIAL_RESOLUTION = "250 m"

# Official SoilGrids v2.0 depth interval labels (verified against GET /properties/layers).
SUPPORTED_DEPTHS: tuple[str, ...] = (
    "0-5cm",
    "5-15cm",
    "15-30cm",
    "30-60cm",
    "60-100cm",
    "100-200cm",
)

COORD_QUANTUM = Decimal("0.0001")


@dataclass(frozen=True)
class PropertySpec:
    key: str
    soilgrids_name: str
    label: str
    display_unit: str
    decimals: int
    fallback_d_factor: int
    # Alternative layer names if the live catalog ever changes. First match wins.
    aliases: tuple[str, ...] = ()


# Mapping verified 2026-09-20 against GET /soilgrids/v2.0/properties/layers:
# phh2o, clay, sand, silt, soc (content, not ocs stock), cec, nitrogen.
PROPERTY_SPECS: tuple[PropertySpec, ...] = (
    PropertySpec("ph", "phh2o", "pH", "", 2, 10, aliases=("ph",)),
    PropertySpec("clay", "clay", "Glina", "%", 1, 10),
    PropertySpec("sand", "sand", "Pesak", "%", 1, 10),
    PropertySpec("silt", "silt", "Prah", "%", 1, 10),
    PropertySpec(
        "organic_carbon",
        "soc",
        "Organski ugljenik",
        "%",
        2,
        10,
        aliases=("socd",),
    ),
    PropertySpec("cec", "cec", "CEC", "cmol(+)/kg", 1, 10),
    PropertySpec("total_nitrogen", "nitrogen", "Ukupni azot", "g/kg", 2, 100, aliases=("n",)),
)

PROPERTY_BY_KEY: dict[str, PropertySpec] = {spec.key: spec for spec in PROPERTY_SPECS}
PROPERTY_BY_LAYER: dict[str, PropertySpec] = {}
for _spec in PROPERTY_SPECS:
    PROPERTY_BY_LAYER[_spec.soilgrids_name] = _spec
    for _alias in _spec.aliases:
        PROPERTY_BY_LAYER.setdefault(_alias, _spec)

REQUESTED_LAYER_NAMES: tuple[str, ...] = tuple(spec.soilgrids_name for spec in PROPERTY_SPECS)

# ocs = organic carbon stock (t/ha). Never treat it as organic carbon content.
EXCLUDED_LAYERS = frozenset({"ocs", "ocd"})


@dataclass
class DepthValue:
    depth: str
    value: float
    unit: str
    uncertainty: float | None = None
    lower: float | None = None
    upper: float | None = None
    raw: float | None = None
    d_factor: int | None = None

    def to_stored(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "uncertainty": self.uncertainty,
            "lower": self.lower,
            "upper": self.upper,
            "raw": self.raw,
            "d_factor": self.d_factor,
        }


@dataclass
class PropertyValues:
    spec: PropertySpec
    depths: dict[str, DepthValue] = field(default_factory=dict)
    target_units: str | None = None
    mapped_units: str | None = None

    def to_stored(self) -> dict[str, Any]:
        return {depth: item.to_stored() for depth, item in self.depths.items()}


@dataclass
class ParseResult:
    status: str
    properties: dict[str, PropertyValues]
    missing_properties: list[str]
    unit_measures: dict[str, dict[str, Any]]
    error: str | None = None

    @property
    def values_payload(self) -> dict[str, dict[str, Any]]:
        return {key: prop.to_stored() for key, prop in self.properties.items()}


def soil_coordinate(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(COORD_QUANTUM, rounding=ROUND_HALF_UP)


def coordinates_are_valid(latitude: Decimal | float | None, longitude: Decimal | float | None) -> bool:
    if latitude is None or longitude is None:
        return False
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return False
    if lat != lat or lon != lon:
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def depth_label(depth_key: str) -> str:
    compact = depth_key.replace(" ", "").replace("–", "-")
    if compact.endswith("cm"):
        span = compact[:-2]
        return f"{span.replace('-', '–')} cm"
    return depth_key


def canonical_depth_key(depth: Any) -> str | None:
    """Accept SoilGrids query depth objects or layer-catalog range strings."""
    if isinstance(depth, str):
        return _normalize_depth_token(depth)
    if not isinstance(depth, dict):
        return None
    label = depth.get("label")
    if isinstance(label, str):
        key = _normalize_depth_token(label)
        if key:
            return key
    range_ = depth.get("range", depth)
    if isinstance(range_, str):
        return _normalize_depth_token(range_)
    if isinstance(range_, dict):
        top = range_.get("top_depth")
        bottom = range_.get("bottom_depth")
        unit = str(range_.get("unit_depth") or "cm").strip() or "cm"
        if top is None or bottom is None:
            return None
        try:
            token = f"{int(top)}-{int(bottom)}{unit}"
        except (TypeError, ValueError):
            return None
        return _normalize_depth_token(token)
    return None


def _normalize_depth_token(token: str) -> str | None:
    compact = token.strip().replace("–", "-").replace(" ", "").lower()
    if compact in SUPPORTED_DEPTHS:
        return compact
    if compact.endswith("cm"):
        candidate = compact
    else:
        candidate = f"{compact}cm"
    return candidate if candidate in SUPPORTED_DEPTHS else None


def resolve_layer_spec(layer_name: str) -> PropertySpec | None:
    return PROPERTY_BY_LAYER.get(layer_name)


def map_requested_layers(available_names: set[str] | list[str] | tuple[str, ...]) -> dict[str, str]:
    """Map AgroTwin property keys to currently advertised SoilGrids layer names."""
    available = {name for name in available_names}
    mapping: dict[str, str] = {}
    for spec in PROPERTY_SPECS:
        if spec.soilgrids_name in available:
            mapping[spec.key] = spec.soilgrids_name
            continue
        for alias in spec.aliases:
            if alias in available:
                mapping[spec.key] = alias
                break
    return mapping


def convert_scaled_value(
    raw: float | int | None,
    d_factor: int | float | None,
    *,
    extra_scale: float = 1.0,
    decimals: int = 2,
) -> float | None:
    if raw is None:
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    factor = float(d_factor) if d_factor not in (None, 0) else 1.0
    converted = (number / factor) * extra_scale
    return _round(converted, decimals)


def extra_scale_for_display(spec: PropertySpec, target_units: str | None) -> float:
    """SOC is stored as g/kg after d_factor; UI uses mass percent."""
    if spec.key != "organic_carbon":
        return 1.0
    units = (target_units or "").strip().lower()
    if units in {"%", "percent"}:
        return 1.0
    if units in {"dg/kg", "dg kg-1"}:
        return 0.01
    # Default SoilGrids soc target_units: g/kg. 10 g/kg = 1%.
    return 0.1


def parse_soilgrids_payload(payload: Any) -> ParseResult:
    if not isinstance(payload, dict):
        return ParseResult("malformed", {}, [spec.key for spec in PROPERTY_SPECS], {}, "malformed_payload")
    properties_block = payload.get("properties")
    if not isinstance(properties_block, dict):
        return ParseResult("malformed", {}, [spec.key for spec in PROPERTY_SPECS], {}, "malformed_payload")
    layers = properties_block.get("layers")
    if not isinstance(layers, list) or not layers:
        return ParseResult("malformed", {}, [spec.key for spec in PROPERTY_SPECS], {}, "malformed_payload")

    parsed: dict[str, PropertyValues] = {}
    unit_measures: dict[str, dict[str, Any]] = {}
    seen_keys: set[str] = set()

    for layer in layers:
        if not isinstance(layer, dict):
            continue
        name = layer.get("name")
        if not isinstance(name, str) or name in EXCLUDED_LAYERS:
            continue
        spec = resolve_layer_spec(name)
        if spec is None:
            continue
        unit_measure = layer.get("unit_measure") if isinstance(layer.get("unit_measure"), dict) else {}
        d_factor = _positive_int(unit_measure.get("d_factor"), spec.fallback_d_factor)
        target_units = unit_measure.get("target_units") if isinstance(unit_measure.get("target_units"), str) else None
        mapped_units = unit_measure.get("mapped_units") if isinstance(unit_measure.get("mapped_units"), str) else None
        extra = extra_scale_for_display(spec, target_units)
        depths: dict[str, DepthValue] = {}
        raw_depths = layer.get("depths")
        if isinstance(raw_depths, list):
            for item in raw_depths:
                parsed_depth = _parse_depth_item(item, spec, d_factor, extra)
                if parsed_depth is None:
                    continue
                depths[parsed_depth.depth] = parsed_depth
        if not depths:
            continue
        parsed[spec.key] = PropertyValues(
            spec=spec,
            depths=depths,
            target_units=target_units,
            mapped_units=mapped_units,
        )
        seen_keys.add(spec.key)
        unit_measures[spec.key] = {
            "soilgrids_name": name,
            "d_factor": d_factor,
            "mapped_units": mapped_units,
            "target_units": target_units,
            "display_unit": spec.display_unit,
            "extra_scale": extra,
        }

    missing = [spec.key for spec in PROPERTY_SPECS if spec.key not in seen_keys]
    if not parsed:
        return ParseResult("malformed", {}, missing, unit_measures, "no_properties")
    status = "partial" if missing else "ok"
    return ParseResult(status, parsed, missing, unit_measures)


def stored_depth_value(payload: Any) -> DepthValue | None:
    if not isinstance(payload, dict) or "value" not in payload:
        return None
    try:
        value = float(payload["value"])
    except (TypeError, ValueError):
        return None
    unit = payload.get("unit") if isinstance(payload.get("unit"), str) else ""
    return DepthValue(
        depth="",
        value=value,
        unit=unit,
        uncertainty=_optional_float(payload.get("uncertainty")),
        lower=_optional_float(payload.get("lower")),
        upper=_optional_float(payload.get("upper")),
        raw=_optional_float(payload.get("raw")),
        d_factor=_positive_int(payload.get("d_factor"), 0) or None,
    )


def _parse_depth_item(
    item: Any,
    spec: PropertySpec,
    d_factor: int,
    extra_scale: float,
) -> DepthValue | None:
    if not isinstance(item, dict):
        return None
    depth_key = canonical_depth_key(item)
    if depth_key is None:
        return None
    values = item.get("values")
    if not isinstance(values, dict):
        return None
    raw_mean = _numeric_or_none(values.get("mean"))
    if raw_mean is None:
        return None
    value = convert_scaled_value(raw_mean, d_factor, extra_scale=extra_scale, decimals=spec.decimals)
    if value is None:
        return None
    return DepthValue(
        depth=depth_key,
        value=value,
        unit=spec.display_unit,
        uncertainty=convert_scaled_value(
            _numeric_or_none(values.get("uncertainty")),
            d_factor,
            extra_scale=extra_scale,
            decimals=spec.decimals,
        ),
        lower=convert_scaled_value(
            _quantile(values, "Q0.05"),
            d_factor,
            extra_scale=extra_scale,
            decimals=spec.decimals,
        ),
        upper=convert_scaled_value(
            _quantile(values, "Q0.95"),
            d_factor,
            extra_scale=extra_scale,
            decimals=spec.decimals,
        ),
        raw=raw_mean,
        d_factor=d_factor,
    )


def _quantile(values: dict[str, Any], name: str) -> float | None:
    if name in values:
        return _numeric_or_none(values.get(name))
    lowered = name.lower()
    for key, raw in values.items():
        if isinstance(key, str) and key.lower() == lowered:
            return _numeric_or_none(raw)
    return None


def _numeric_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _optional_float(value: Any) -> float | None:
    return _numeric_or_none(value)


def _positive_int(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _round(value: float, digits: int) -> float:
    quantum = Decimal("1").scaleb(-digits)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))
