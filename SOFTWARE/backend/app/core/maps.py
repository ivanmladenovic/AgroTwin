from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx

_ALLOWED_HOST_SUFFIXES = ("google.com", "google.rs", "goo.gl")
_COORD = r"(-?\d+(?:\.\d+)?)"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_MAPS_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml",
}
_GEOCODE_HEADERS = {"User-Agent": "AgroTwin/1.0 (orchard dashboard map)"}


@dataclass(frozen=True)
class LatLng:
    lat: float
    lng: float


def normalize_maps_url(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parsed = urlparse(text)
    host = parsed.netloc.lower().split("@")[-1]
    if host.startswith("www."):
        host = host[4:]
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("Unesite ispravan Google Maps link")
    if not any(host == suffix or host.endswith(f".{suffix}") for suffix in _ALLOWED_HOST_SUFFIXES):
        raise ValueError("Unesite Google Maps link (maps.google.com ili maps.app.goo.gl)")
    return text


def is_valid_coord(lat: float, lng: float) -> bool:
    return math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180


def _to_latlng(lat_raw: str, lng_raw: str) -> LatLng | None:
    try:
        lat = float(lat_raw)
        lng = float(lng_raw)
    except ValueError:
        return None
    if not is_valid_coord(lat, lng):
        return None
    return LatLng(lat=lat, lng=lng)


def parse_google_maps_url(input_value: str) -> LatLng | None:
    raw = input_value.strip()
    if not raw:
        return None

    plain = re.match(rf"^{_COORD}\s*,\s*\+?{_COORD}$", raw)
    if plain:
        return _to_latlng(plain.group(1), plain.group(2))

    href = raw
    try:
        parsed_url = urlparse(raw)
        href = unquote(parsed_url.geturl())
    except ValueError:
        return None

    at_match = re.search(rf"@{_COORD},{_COORD}", href)
    if at_match:
        return _to_latlng(at_match.group(1), at_match.group(2))

    data_match = re.search(rf"!3d{_COORD}!4d{_COORD}", href)
    if data_match:
        return _to_latlng(data_match.group(1), data_match.group(2))

    search_match = re.search(rf"/maps/search/{_COORD},\+?{_COORD}", href)
    if search_match:
        return _to_latlng(search_match.group(1), search_match.group(2))

    dir_match = re.search(rf"/maps/dir/{_COORD},\+?{_COORD}", href)
    if dir_match:
        return _to_latlng(dir_match.group(1), dir_match.group(2))

    place_coord_match = re.search(rf"/maps/place/{_COORD},\+?{_COORD}", href)
    if place_coord_match:
        return _to_latlng(place_coord_match.group(1), place_coord_match.group(2))

    query = parse_qs(urlparse(href).query)
    for key in ("q", "query", "ll", "center", "destination"):
        values = query.get(key) or []
        for value in values:
            pair = re.search(rf"{_COORD}\s*,\s*\+?{_COORD}", value)
            if pair:
                found = _to_latlng(pair.group(1), pair.group(2))
                if found:
                    return found

    return None


def is_google_maps_host(hostname: str) -> bool:
    host = hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    return (
        bool(re.search(r"(^|\.)google\.[a-z.]+$", host))
        or bool(re.search(r"(^|\.)goo\.gl$", host))
        or host == "maps.app.goo.gl"
    )


def extract_place_query(input_value: str) -> str | None:
    href = unquote(input_value.strip())
    match = re.search(r"/maps/place/([^/@?]+)", href)
    if not match:
        return None
    name = unquote(match.group(1)).replace("+", " ").strip()
    if not name or parse_google_maps_url(name):
        return None
    return name


def expand_maps_short_link(start_url: str) -> str:
    current = start_url
    with httpx.Client(follow_redirects=False, timeout=8.0, headers=_MAPS_HEADERS) as client:
        for _ in range(6):
            response = client.get(current)
            location = response.headers.get("location")
            if location and 300 <= response.status_code < 400:
                current = urljoin(current, location)
                if parse_google_maps_url(current):
                    return current
                continue
            if response.status_code == 200 and not parse_google_maps_url(current):
                followed = client.build_request("GET", start_url)
                with httpx.Client(follow_redirects=True, timeout=8.0, headers=_MAPS_HEADERS) as follower:
                    resolved = follower.send(followed)
                    if parse_google_maps_url(str(resolved.url)):
                        return str(resolved.url)
                    html = resolved.text
                    from_html = re.search(r"maps/search/(-?\d+\.\d+),\+?(-?\d+\.\d+)", html)
                    if from_html:
                        return f"https://www.google.com/maps/search/{from_html.group(1)},{from_html.group(2)}"
            return str(response.url) if response.url else current
    return current


def geocode_place(query: str) -> LatLng | None:
    text = query.strip()
    if not text:
        return None
    lowered = text.lower()
    if not any(token in lowered for token in ("srbija", "serbia", "hrvatska", "croatia", "bosna", "bosnia")):
        text = f"{text}, Serbia"
    try:
        with httpx.Client(timeout=8.0, headers=_GEOCODE_HEADERS) as client:
            response = client.get(_NOMINATIM_URL, params={"q": text, "format": "json", "limit": 1})
            response.raise_for_status()
            rows = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    if not isinstance(first, dict):
        return None
    try:
        return LatLng(lat=float(first["lat"]), lng=float(first["lon"]))
    except (KeyError, TypeError, ValueError):
        return None


def resolve_maps_location(input_value: str | None, fallback_query: str | None = None) -> LatLng | None:
    raw = (input_value or "").strip()
    if raw:
        direct = parse_google_maps_url(raw)
        if direct:
            return direct
        parsed_url = urlparse(raw)
        if parsed_url.hostname and is_google_maps_host(parsed_url.hostname):
            try:
                expanded = expand_maps_short_link(raw)
                parsed = parse_google_maps_url(expanded)
                if parsed:
                    return parsed
            except httpx.HTTPError:
                pass
            place = extract_place_query(raw)
            if place:
                geocoded = geocode_place(place)
                if geocoded:
                    return geocoded
    if fallback_query:
        return geocode_place(fallback_query)
    return None


def coordinates_as_decimal(location: LatLng) -> tuple[Decimal, Decimal]:
    return (
        Decimal(str(round(location.lat, 6))),
        Decimal(str(round(location.lng, 6))),
    )
