from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.maps import extract_place_query, parse_google_maps_url


def assert_coord(label: str, value: str, lat: float, lng: float) -> None:
    parsed = parse_google_maps_url(value)
    assert parsed is not None, f"Failed to parse: {label}"
    assert abs(parsed.lat - lat) < 1e-6, f"{label} lat {parsed.lat} != {lat}"
    assert abs(parsed.lng - lng) < 1e-6, f"{label} lng {parsed.lng} != {lng}"


def verify_maps_parsing() -> None:
    assert_coord("plain pair", "44.8125, 20.4612", 44.8125, 20.4612)
    assert_coord("at pin", "https://www.google.com/maps/@44.8125,20.4612,17z", 44.8125, 20.4612)
    assert_coord(
        "place with at",
        "https://www.google.com/maps/place/Belgrade/@44.8125,20.4612,12z",
        44.8125,
        20.4612,
    )
    assert_coord(
        "3d4d",
        "https://www.google.com/maps/place/Foo/data=!3d44.8125!4d20.4612",
        44.8125,
        20.4612,
    )
    assert_coord("q param", "https://www.google.com/maps?q=44.8125,20.4612", 44.8125, 20.4612)
    assert_coord(
        "search path with plus",
        "https://www.google.com/maps/search/44.257400,+21.102738?entry=tts",
        44.2574,
        21.102738,
    )
    assert parse_google_maps_url("https://maps.app.goo.gl/dgTHLxRLcCsTKiNz9") is None
    assert extract_place_query("https://www.google.com/maps/place/Kusiljevo") == "Kusiljevo"
    print("maps parsing checks passed")


if __name__ == "__main__":
    verify_maps_parsing()
