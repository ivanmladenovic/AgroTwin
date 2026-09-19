from unittest import TestCase

import httpx

from app.services.weather_provider import YR_COMPACT_URL, YrWeatherError, YrWeatherProvider


SAMPLE = {
    "properties": {
        "meta": {"updated_at": "2026-09-15T06:00:00Z"},
        "timeseries": [
            {
                "time": "2026-09-15T06:00:00Z",
                "data": {
                    "instant": {"details": {"air_temperature": 18.2}},
                    "next_1_hours": {
                        "summary": {"symbol_code": "partlycloudy_day"},
                        "details": {"precipitation_amount": 0.0},
                    },
                },
            }
        ],
    }
}


class YrWeatherProviderTests(TestCase):
    def test_successful_request_uses_https_and_user_agent(self) -> None:
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["scheme"] = request.url.scheme
            seen["url"] = str(request.url)
            seen["ua"] = request.headers.get("User-Agent", "")
            self.assertNotIn("If-Modified-Since", request.headers)
            return httpx.Response(
                200,
                json=SAMPLE,
                headers={"Last-Modified": "Tue, 15 Sep 2026 06:00:00 GMT"},
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = YrWeatherProvider(client=client, user_agent="AgroTwin/1.0 (contact@agrotwin.com)")
        result = provider.fetch(44.123456, 21.987654)
        self.assertEqual(seen["scheme"], "https")
        self.assertTrue(seen["url"].startswith(YR_COMPACT_URL))
        self.assertIn("lat=44.1235", seen["url"])
        self.assertIn("lon=21.9877", seen["url"])
        self.assertEqual(seen["ua"], "AgroTwin/1.0 (contact@agrotwin.com)")
        self.assertFalse(result.not_modified)
        self.assertEqual(result.last_modified, "Tue, 15 Sep 2026 06:00:00 GMT")
        self.assertIsNotNone(result.payload)

    def test_not_modified(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers.get("If-Modified-Since"), "Tue, 15 Sep 2026 06:00:00 GMT")
            return httpx.Response(304)

        provider = YrWeatherProvider(
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            user_agent="AgroTwin/1.0 (contact@agrotwin.com)",
        )
        result = provider.fetch(44.1, 21.1, last_modified="Tue, 15 Sep 2026 06:00:00 GMT")
        self.assertTrue(result.not_modified)
        self.assertIsNone(result.payload)

    def test_error_status_codes(self) -> None:
        for status in (403, 404, 429, 500):

            def handler(_request: httpx.Request, code=status) -> httpx.Response:
                return httpx.Response(code)

            provider = YrWeatherProvider(
                client=httpx.Client(transport=httpx.MockTransport(handler)),
                user_agent="AgroTwin/1.0 (contact@agrotwin.com)",
            )
            with self.assertRaises(YrWeatherError) as raised:
                provider.fetch(44.1, 21.1)
            self.assertEqual(raised.exception.status_code, status)
