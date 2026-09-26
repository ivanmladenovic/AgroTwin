"""Developer guide: AI Model Benchmark

Compare Google Gemini 3.8 Flash and OpenAI GPT-5 on identical AgroTwin test inputs.

This is a developer/admin tool. It is not the production AI Agronom and does not
perform model routing or automatic scoring.

## 1. API keys (backend only)

Put keys in `SOFTWARE/backend/.env` (or `SOFTWARE/.env`):

```bash
GEMINI_API_KEY=
OPENAI_API_KEY=
```

Never put keys in frontend `.env`, localStorage, the database, or documentation
with real values. The frontend only calls AgroTwin backend endpoints.

Optional model / pricing overrides (same files):

```bash
GEMINI_MODEL=gemini-3.8-flash
OPENAI_BENCHMARK_MODEL=gpt-5
BENCHMARK_GEMINI_INPUT_USD_PER_MTOK=0.75
BENCHMARK_GEMINI_OUTPUT_USD_PER_MTOK=3.75
BENCHMARK_OPENAI_INPUT_USD_PER_MTOK=1.25
BENCHMARK_OPENAI_OUTPUT_USD_PER_MTOK=10.0
```

After changing env vars, restart the API process.

## 2. Start the application

From `SOFTWARE/`:

```bash
docker compose up -d db
cd backend && source .venv/bin/activate
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8001
```

In another terminal:

```bash
cd frontend && npm run dev
```

Demo admin (superuser after seed): `admin@agrotwin.rs` / `admin`

## 3. Open the benchmark page

URL: [http://localhost:5174/dev/benchmark](http://localhost:5174/dev/benchmark)

Only users with `is_superuser=true` can open the page or call `/api/v1/benchmark/*`.
The route is intentionally absent from normal navigation.

## 4. Run a text test

1. Click **TEST 1 — General agricultural reasoning** (or write your own prompt).
2. Mode: Text only.
3. Enable Gemini and/or GPT-5.
4. Click **Run comparison**.

## 5. Run an image test

1. Load **TEST 2** or set mode to Image + text.
2. Upload a JPEG/PNG/WebP (max 8 MB, max edge 4096 px) or paste an AgroTwin photo UUID.
3. Run comparison. Both providers receive the same image bytes.

## 6. Run a Context / evidence test

1. Load TEST 3–5 or paste JSON into Context / Knowledge evidence.
2. Mode `image_context` or `full` as needed.
3. Run comparison. The same JSON is embedded into the user message for every model.

## 7. Interpreting latency / tokens / cost

- **Latency**: wall-clock ms for that provider call.
- **Tokens**: values returned by the provider. If missing → **N/A** (never invented).
- **Estimated cost**: `tokens × configured USD / 1M`. If tokens are missing → **N/A**.
- Pricing is configuration, not a billing invoice.

## 8. Change model IDs

Set `GEMINI_MODEL` / `OPENAI_BENCHMARK_MODEL` in backend env and restart.

## 9. Update pricing

Set `BENCHMARK_*_USD_PER_MTOK` variables in backend env and restart. Values are
also shown (without secrets) via `GET /api/v1/benchmark/config`.

## 10. API endpoints

- `GET /api/v1/benchmark/config` — models, defaults, pricing, presets (no keys)
- `POST /api/v1/benchmark/run` — multipart form comparison

## Notes

- Web search / grounding is disabled for both providers.
- One provider failure does not cancel the other.
- V1 does not persist benchmark history.
"""
