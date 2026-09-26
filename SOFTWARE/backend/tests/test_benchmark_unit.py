from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch
import sys

from PIL import Image

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.benchmark.image import validate_benchmark_image
from app.benchmark.message import build_user_message
from app.benchmark.pricing import estimate_cost_usd
from app.benchmark.providers.gemini import GeminiBenchmarkProvider
from app.benchmark.providers.openai import OpenAIBenchmarkProvider
from app.benchmark.runner import run_benchmark
from app.benchmark.types import (
    BenchmarkImage,
    BenchmarkInput,
    BenchmarkMode,
    GenerationSettings,
    ProviderId,
    ProviderResult,
    TokenUsage,
)
from app.core.config import Settings
from app.core.exceptions import AppError


def _settings(**overrides) -> Settings:
    base = {
        "secret_key": "x" * 40,
        "gemini_api_key": "gemini-test-key",
        "openai_api_key": "openai-test-key",
        "gemini_model": "gemini-3.8-flash",
        "openai_benchmark_model": "gpt-5",
        "benchmark_gemini_input_usd_per_mtok": 0.75,
        "benchmark_gemini_output_usd_per_mtok": 3.75,
        "benchmark_openai_input_usd_per_mtok": 1.25,
        "benchmark_openai_output_usd_per_mtok": 10.0,
    }
    base.update(overrides)
    return Settings(**base)


def _png_bytes(size: tuple[int, int] = (64, 64)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, (20, 120, 40)).save(buf, format="PNG")
    return buf.getvalue()


class PricingTests(TestCase):
    def test_cost_uses_configured_rates(self) -> None:
        settings = _settings()
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
        self.assertEqual(estimate_cost_usd("gemini", usage, settings), 4.5)
        self.assertEqual(estimate_cost_usd("openai", usage, settings), 11.25)

    def test_missing_tokens_return_none(self) -> None:
        settings = _settings()
        self.assertIsNone(estimate_cost_usd("gemini", TokenUsage(input_tokens=10), settings))
        self.assertIsNone(estimate_cost_usd("openai", TokenUsage(), settings))


class ImageValidationTests(TestCase):
    def test_accepts_png(self) -> None:
        image = validate_benchmark_image(
            _png_bytes(),
            mime_type="image/png",
            filename="leaf.png",
            settings=_settings(),
        )
        self.assertEqual(image.mime_type, "image/png")
        self.assertEqual(image.width, 64)

    def test_rejects_oversized_file(self) -> None:
        settings = _settings(benchmark_max_image_bytes=100)
        with self.assertRaises(AppError) as ctx:
            validate_benchmark_image(
                _png_bytes((200, 200)),
                mime_type="image/png",
                filename="big.png",
                settings=settings,
            )
        self.assertEqual(ctx.exception.code, "image_too_large")

    def test_rejects_invalid_type(self) -> None:
        with self.assertRaises(AppError) as ctx:
            validate_benchmark_image(
                b"%PDF-1.4",
                mime_type="application/pdf",
                filename="doc.pdf",
                settings=_settings(),
            )
        self.assertEqual(ctx.exception.code, "invalid_image")


class MessageAssemblyTests(TestCase):
    def test_same_payload_includes_context_and_evidence(self) -> None:
        text = build_user_message(
            prompt="What can you conclude?",
            mode=BenchmarkMode.FULL,
            context={"parcel": {"name": "A"}},
            knowledge_evidence=[{"source": "Manual", "content": "Note"}],
            has_image=True,
        )
        self.assertIn("What can you conclude?", text)
        self.assertIn("AgroTwin Context", text)
        self.assertIn("Knowledge evidence", text)
        self.assertIn("image is attached", text)


class ProviderConstructionTests(TestCase):
    def test_missing_gemini_key(self) -> None:
        provider = GeminiBenchmarkProvider(_settings(gemini_api_key=None))
        result = provider.generate(
            system_instruction="sys",
            user_text="hello",
            image=None,
            settings=GenerationSettings(temperature=0.2, max_output_tokens=128),
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.error_code, "missing_api_key")
        self.assertNotIn("gemini-test-key", result.error_message or "")

    def test_missing_openai_key(self) -> None:
        provider = OpenAIBenchmarkProvider(_settings(openai_api_key=None))
        result = provider.generate(
            system_instruction="sys",
            user_text="hello",
            image=None,
            settings=GenerationSettings(temperature=0.2, max_output_tokens=128),
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.error_code, "missing_api_key")

    @patch("app.benchmark.providers.gemini.httpx.post")
    def test_gemini_request_shape(self, post: MagicMock) -> None:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
        }
        post.return_value = response
        image = BenchmarkImage(content=_png_bytes(), mime_type="image/png", filename="a.png", width=64, height=64)
        provider = GeminiBenchmarkProvider(_settings())
        result = provider.generate(
            system_instruction="sys-bench",
            user_text="user-bench",
            image=image,
            settings=GenerationSettings(temperature=0.2, max_output_tokens=256),
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(result.response_text, "ok")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "gemini-test-key")
        payload = kwargs["json"]
        self.assertEqual(payload["systemInstruction"]["parts"][0]["text"], "sys-bench")
        self.assertEqual(payload["contents"][0]["parts"][0]["text"], "user-bench")
        self.assertIn("inline_data", payload["contents"][0]["parts"][1])
        self.assertNotIn("tools", payload)
        self.assertNotIn("googleSearch", str(payload))

    @patch("app.benchmark.providers.openai.httpx.post")
    def test_openai_request_shape(self, post: MagicMock) -> None:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "model": "gpt-5",
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
        }
        post.return_value = response
        image = BenchmarkImage(content=_png_bytes(), mime_type="image/png", filename="a.png", width=64, height=64)
        provider = OpenAIBenchmarkProvider(_settings())
        result = provider.generate(
            system_instruction="sys-bench",
            user_text="user-bench",
            image=image,
            settings=GenerationSettings(temperature=0.2, max_output_tokens=256),
        )
        self.assertEqual(result.status, "success")
        kwargs = post.call_args.kwargs
        self.assertTrue(kwargs["headers"]["Authorization"].startswith("Bearer "))
        payload = kwargs["json"]
        self.assertEqual(payload["model"], "gpt-5")
        self.assertEqual(payload["messages"][0]["content"], "sys-bench")
        self.assertEqual(payload["messages"][1]["content"][0]["text"], "user-bench")
        self.assertEqual(payload["max_completion_tokens"], 256)
        self.assertNotIn("tools", payload)
        self.assertNotIn("web_search", payload)


class RunnerIsolationTests(TestCase):
    def test_same_input_sent_to_both_and_failure_isolated(self) -> None:
        captured: list[tuple[str, str, str | None]] = []

        class FakeGemini:
            provider_id = "gemini"
            model = "gemini-3.8-flash"

            def generate(self, *, system_instruction, user_text, image, settings):
                captured.append(("gemini", user_text, system_instruction))
                now = datetime.now(timezone.utc)
                return ProviderResult(
                    provider="gemini",
                    model=self.model,
                    status="success",
                    started_at=now,
                    ended_at=now,
                    latency_ms=1,
                    response_text="g-ok",
                    usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
                )

        class FakeOpenAI:
            provider_id = "openai"
            model = "gpt-5"

            def generate(self, *, system_instruction, user_text, image, settings):
                captured.append(("openai", user_text, system_instruction))
                raise RuntimeError("boom")

        settings = _settings()
        with patch(
            "app.benchmark.runner._resolve_providers",
            return_value=[FakeGemini(), FakeOpenAI()],
        ):
            result = run_benchmark(
                BenchmarkInput(
                    test_name="iso",
                    mode=BenchmarkMode.TEXT,
                    prompt="Shared prompt",
                    system_instruction="Shared system",
                    context={"a": 1},
                    knowledge_evidence=[{"b": 2}],
                    providers=[ProviderId.GEMINI, ProviderId.OPENAI],
                    settings=GenerationSettings(temperature=0.2, max_output_tokens=64),
                ),
                settings,
            )
        self.assertEqual(len(result.results), 2)
        by_provider = {item.provider: item for item in result.results}
        self.assertEqual(by_provider["gemini"].status, "success")
        self.assertEqual(by_provider["openai"].status, "error")
        self.assertEqual(captured[0][1], captured[1][1])
        self.assertEqual(captured[0][2], captured[1][2])
        self.assertIn("Shared prompt", captured[0][1])
        self.assertIn('"a": 1', captured[0][1])
        body = str(result)
        self.assertNotIn("gemini-test-key", body)
        self.assertNotIn("openai-test-key", body)
