from unittest import TestCase

from app.ai import openai_compatible as mod


class StickyFallbackTests(TestCase):
    def setUp(self) -> None:
        mod._clear_sticky_model()

    def tearDown(self) -> None:
        mod._clear_sticky_model()

    def test_candidates_prefer_sticky_before_primary(self) -> None:
        mod._set_sticky_model("gemini-3.5-flash")
        models = mod._chat_model_candidates(
            "gemini-3.1-flash-lite",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        self.assertEqual(models[0], "gemini-3.5-flash")
        self.assertEqual(models[1], "gemini-3.1-flash-lite")
        self.assertIn("gemini-3.8-flash", models)

    def test_candidates_without_sticky_start_at_primary(self) -> None:
        models = mod._chat_model_candidates(
            "gemini-3.1-flash-lite",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        self.assertEqual(models[0], "gemini-3.1-flash-lite")
