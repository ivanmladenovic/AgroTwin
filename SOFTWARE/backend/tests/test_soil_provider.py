from __future__ import annotations

from pathlib import Path
from unittest import TestCase
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import httpx

from app.soil.properties import REQUESTED_LAYER_NAMES, SUPPORTED_DEPTHS
from app.soil.provider import SOILGRIDS_QUERY_PATH, SoilGridsError, SoilGridsProvider
from app.soil.rate_limit import SoilGridsRateLimiter

SAMPLE = {
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [21.1027, 44.2574]},
    "properties": {"layers": [{"name": "phh2o", "depths": []}]},
}


class SoilGridsProviderTests(TestCase):
    def test_single_https_query_requests_all_layers(self) -> None:
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["scheme"] = request.url.scheme
            seen["url"] = str(request.url)
            seen["ua"] = request.headers.get("User-Agent", "")
            return httpx.Response(200, json=SAMPLE)

        limiter = SoilGridsRateLimiter(min_interval=0)
        provider = SoilGridsProvider(
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            limiter=limiter,
            user_agent="AgroTwin/1.0 (contact@agrotwin.com)",
            base_url="https://rest.isric.org",
        )
        result = provider.fetch(44.2574, 21.102738)
        self.assertEqual(seen["scheme"], "https")
        self.assertIn(SOILGRIDS_QUERY_PATH, seen["url"])
        for name in REQUESTED_LAYER_NAMES:
            self.assertIn(f"property={name}", seen["url"])
        for depth in SUPPORTED_DEPTHS:
            self.assertIn(f"depth={depth}", seen["url"])
        self.assertIn("value=mean", seen["url"])
        self.assertEqual(seen["ua"], "AgroTwin/1.0 (contact@agrotwin.com)")
        self.assertEqual(result.dataset_version, "2.0")
        self.assertEqual(result.payload["type"], "Feature")

    def test_timeout_and_rate_limit_status(self) -> None:
        def timeout_handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow")

        provider = SoilGridsProvider(
            client=httpx.Client(transport=httpx.MockTransport(timeout_handler)),
            limiter=SoilGridsRateLimiter(min_interval=0),
        )
        with self.assertRaises(SoilGridsError) as timeout_error:
            provider.fetch(44.1, 21.1)
        self.assertEqual(timeout_error.exception.code, "timeout")

        def limited(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429)

        limited_provider = SoilGridsProvider(
            client=httpx.Client(transport=httpx.MockTransport(limited)),
            limiter=SoilGridsRateLimiter(min_interval=0),
        )
        with self.assertRaises(SoilGridsError) as rate_error:
            limited_provider.fetch(44.1, 21.1)
        self.assertEqual(rate_error.exception.code, "rate_limited")

    def test_malformed_json(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not-json")

        provider = SoilGridsProvider(
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            limiter=SoilGridsRateLimiter(min_interval=0),
        )
        with self.assertRaises(SoilGridsError) as raised:
            provider.fetch(44.1, 21.1)
        self.assertEqual(raised.exception.code, "malformed")

    def test_local_rate_limiter_blocks_burst(self) -> None:
        limiter = SoilGridsRateLimiter(min_interval=60)
        self.assertTrue(limiter.acquire())
        self.assertFalse(limiter.acquire())

        calls = {"n": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=SAMPLE)

        provider = SoilGridsProvider(
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            limiter=limiter,
        )
        with self.assertRaises(SoilGridsError) as raised:
            provider.fetch(44.1, 21.1)
        self.assertEqual(raised.exception.code, "rate_limited")
        self.assertEqual(calls["n"], 0)
