from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.ai import openai_compatible as mod
from app.ai.base import ChatMessage
from app.core.config import Settings
from app.core.exceptions import AppError


class StickyFallbackTests(TestCase):
    def setUp(self) -> None:
        mod._reset_runtime_state()

    def tearDown(self) -> None:
        mod._reset_runtime_state()

    def test_candidates_prefer_sticky_before_primary(self) -> None:
        mod._set_sticky("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-3.8-flash")
        models = mod._chat_model_candidates(
            "gemini-3.5-flash",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        self.assertEqual(models[0], "gemini-3.8-flash")
        self.assertEqual(models[1], "gemini-3.5-flash")
        self.assertIn("gemini-flash-latest", models)

    def test_candidates_without_sticky_start_at_primary(self) -> None:
        models = mod._chat_model_candidates(
            "gemini-3.5-flash",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        self.assertEqual(models[0], "gemini-3.5-flash")
        self.assertNotIn("gemini-3.1-flash-lite", models)

    def test_openai_targets_after_gemini(self) -> None:
        settings = MagicMock(spec=Settings)
        settings.ai_api_key = "gemini-key"
        settings.ai_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        settings.ai_chat_model = "gemini-3.5-flash"
        settings.ai_embedding_model = "gemini-embedding-001"
        settings.ai_vision_model = "gemini-3.5-flash"
        settings.ai_embedding_dim = 1536
        settings.openai_api_key = "openai-key"
        settings.ai_openai_base_url = "https://api.openai.com/v1"
        settings.ai_openai_fallback_models = "gpt-4.1-mini,gpt-4o"
        provider = mod.OpenAICompatibleProvider(settings)
        targets = provider._chat_targets()
        labels_models = [(t.provider_label, t.model) for t in targets]
        self.assertEqual(labels_models[0], ("gemini", "gemini-3.5-flash"))
        self.assertIn(("openai", "gpt-4.1-mini"), labels_models)
        self.assertIn(("openai", "gpt-4o"), labels_models)
        # OpenAI comes after Gemini models.
        openai_idx = labels_models.index(("openai", "gpt-4.1-mini"))
        gemini_idx = labels_models.index(("gemini", "gemini-3.5-flash"))
        self.assertGreater(openai_idx, gemini_idx)

    def test_circuit_skips_gemini_when_openai_available(self) -> None:
        settings = MagicMock(spec=Settings)
        settings.ai_api_key = "gemini-key"
        settings.ai_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        settings.ai_chat_model = "gemini-3.5-flash"
        settings.ai_embedding_model = "gemini-embedding-001"
        settings.ai_vision_model = "gemini-3.5-flash"
        settings.ai_embedding_dim = 1536
        settings.openai_api_key = "openai-key"
        settings.ai_openai_base_url = "https://api.openai.com/v1"
        settings.ai_openai_fallback_models = "gpt-4.1-mini,gpt-4o"
        provider = mod.OpenAICompatibleProvider(settings)
        mod._record_gemini_capacity_failure()
        mod._record_gemini_capacity_failure()
        self.assertTrue(mod._gemini_circuit_open())
        targets = provider._chat_targets()
        self.assertEqual(targets[0].provider_label, "openai")
        self.assertEqual(targets[0].model, "gpt-4.1-mini")

    def test_chat_falls_through_to_openai(self) -> None:
        settings = MagicMock(spec=Settings)
        settings.ai_api_key = "gemini-key"
        settings.ai_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        settings.ai_chat_model = "gemini-3.5-flash"
        settings.ai_embedding_model = "gemini-embedding-001"
        settings.ai_vision_model = "gemini-3.5-flash"
        settings.ai_embedding_dim = 1536
        settings.openai_api_key = "openai-key"
        settings.ai_openai_base_url = "https://api.openai.com/v1"
        settings.ai_openai_fallback_models = "gpt-4.1-mini"
        provider = mod.OpenAICompatibleProvider(settings)

        def fake_post(base_url, api_key, path, payload):
            if "generativelanguage" in base_url:
                raise AppError("AI provajder je vratio 503: high demand", status_code=502, code="ai_unavailable")
            return {
                "model": payload["model"],
                "choices": [{"message": {"role": "assistant", "content": "Odgovor sa OpenAI"}}],
            }

        with patch.object(provider, "_post", side_effect=fake_post):
            result = provider.chat([ChatMessage(role="user", content="Zdravo")])
        self.assertEqual(result.content, "Odgovor sa OpenAI")
        self.assertEqual(result.model, "gpt-4.1-mini")
