from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
import sys

from PIL import Image
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.seed import DEMO_EMAIL, DEMO_PASSWORD
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.benchmark.types import ProviderResult, TokenUsage
from datetime import datetime, timezone


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _ensure_superuser() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == DEMO_EMAIL).one()
        if not user.is_superuser:
            user.is_superuser = True
            db.commit()
    finally:
        db.close()


def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (48, 48), (10, 80, 20)).save(buf, format="PNG")
    return buf.getvalue()


def _fake_result(provider: str, status: str = "success") -> ProviderResult:
    now = datetime.now(timezone.utc)
    return ProviderResult(
        provider=provider,
        model="fake",
        status=status,
        started_at=now,
        ended_at=now,
        latency_ms=12,
        response_text="ok" if status == "success" else None,
        error_code=None if status == "success" else "provider_error",
        error_message=None if status == "success" else "failed",
        usage=TokenUsage(input_tokens=11, output_tokens=3, total_tokens=14),
        estimated_cost_usd=0.0001 if status == "success" else None,
        generation_settings={"temperature": 0.2},
        metadata_notes=[],
        raw_metadata={},
    )


class BenchmarkApiTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_superuser()
        cls.client = TestClient(app)
        cls.headers = _auth(cls.client)

    def test_config_requires_auth(self) -> None:
        response = self.client.get("/api/v1/benchmark/config")
        self.assertEqual(response.status_code, 401)

    def test_config_for_superuser_hides_keys(self) -> None:
        response = self.client.get("/api/v1/benchmark/config", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        dumped = str(body)
        self.assertNotIn("api_key", dumped.lower())
        self.assertNotIn("GEMINI_API_KEY", dumped)
        self.assertNotIn("OPENAI_API_KEY", dumped)
        self.assertIn("models", body)
        self.assertIn("pricing", body)
        self.assertIn("test_cases", body)
        me = self.client.get("/api/v1/auth/me", headers=self.headers)
        self.assertTrue(me.json().get("is_superuser"))

    def test_non_superuser_forbidden(self) -> None:
        from app.core.security import hash_password

        email = f"bench-{uuid4().hex[:8]}@example.com"
        db = SessionLocal()
        try:
            user = User(
                email=email,
                hashed_password=hash_password("password123"),
                full_name="Regular User",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        login = self.client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
        self.assertEqual(login.status_code, 200, login.text)
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        response = self.client.get("/api/v1/benchmark/config", headers=headers)
        self.assertEqual(response.status_code, 403)

    @patch("app.benchmark.service.run_benchmark")
    def test_run_comparison_multipart(self, run_mock) -> None:
        from app.benchmark.types import BenchmarkMode, BenchmarkResult

        now = datetime.now(timezone.utc)

        def fake_run(payload, settings=None):
            self.assertEqual(payload.prompt, "Shared prompt")
            self.assertEqual(payload.providers[0].value, "gemini")
            self.assertIsNotNone(payload.image)
            return BenchmarkResult(
                test_name=payload.test_name,
                mode=payload.mode,
                has_image=True,
                prompt_preview=payload.prompt,
                system_instruction=payload.system_instruction,
                generation_settings={"temperature": 0.2},
                equivalence_notes=["same input"],
                results=[_fake_result("gemini"), _fake_result("openai", status="error")],
                ran_at=now,
            )

        run_mock.side_effect = fake_run
        response = self.client.post(
            "/api/v1/benchmark/run",
            headers=self.headers,
            data={
                "test_name": "Image case",
                "mode": "image",
                "prompt": "Shared prompt",
                "providers": "gemini,openai",
                "context_json": '{"parcel":{"name":"T"}}',
            },
            files={"image": ("leaf.png", _png(), "image/png")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["results"][0]["status"], "success")
        self.assertEqual(body["results"][1]["status"], "error")
        self.assertNotIn("winner", body)
        self.assertNotIn("score", body)
        self.assertNotIn("ranking", str(body).lower())

    def test_invalid_context_json(self) -> None:
        response = self.client.post(
            "/api/v1/benchmark/run",
            headers=self.headers,
            data={
                "test_name": "bad json",
                "mode": "text",
                "prompt": "hi",
                "providers": "gemini",
                "context_json": "{not-json",
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json().get("code"), "invalid_json")
