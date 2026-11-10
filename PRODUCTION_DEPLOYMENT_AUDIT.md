# AgroTwin — Production Deployment Audit

**Datum:** 2026-11-08  
**Opseg:** ceo monorepo `AgroTwin` (`SOFTWARE/`, `Website/`, `render.yaml`)  
**Režim:** read-only analiza — **nema** izmena koda, paketa ni migracija  
**Svrha:** tehnička dokumentacija za produkcioni deployment, rizici i procedura migracije

---

## 1. Rezime arhitekture

AgroTwin je monorepo sa **tri deployabilne površine**:

| Komponenta | Putanja | Runtime | Uloga |
|---|---|---|---|
| Product API | `SOFTWARE/backend/` | Python 3.12, FastAPI, Uvicorn | REST API, auth, storage, AI, satelit |
| Product UI | `SOFTWARE/frontend/` | React 19 + Vite SPA (static `dist/`) | Autentikovana aplikacija |
| Marketing | `Website/` | React 19 + Vite SPA (static `dist/`) | Javni sajt / lead gen |

**Baza:** PostgreSQL 16 (+ opciono **pgvector** ekstenzija).  
**Lokalni compose:** `SOFTWARE/docker-compose.yml` (`pgvector/pgvector:pg16`, API `:8001`, UI `:5174`).  
**Cloud blueprint:** root `render.yaml` (Postgres + Docker API + static UI).

```
Browser
  ├─ myagrotwin.com          → Website (static)
  └─ app.myagrotwin.com      → SOFTWARE/frontend (static SPA)
         │  Authorization: Bearer <JWT>
         ▼
      API  /api/v1/*         → SOFTWARE/backend (FastAPI)
         ├─ PostgreSQL (+ vector)
         ├─ Object storage (local ili S3/R2)
         └─ spoljni API-ji (Gemini/OpenAI, Met.no, SoilGrids, Copernicus)
```

**Zaključak fit-a:** produkcija zahteva **zaseban Python/API proces (Docker/VPS/PaaS) + managed Postgres + trajni object storage + cron**. Tipičan PHP shared hosting **nije** pogodan za API; marketing i (delimično) SPA frontend mogu na static/CDN/Apache.

---

## 2. Frontend — product app (`SOFTWARE/frontend`)

### 2.1 Struktura

- Entry: `src/main.tsx` → `src/app/App.tsx`
- Layout / guards: `src/app/AppLayout.tsx`, `src/app/route-guards.tsx`
- Feature moduli: `src/features/{auth,dashboard,orchard,journal,agronomist,enterprise,satellite,planning,workforce,compliance,passport,...}/`
- Shared: `src/shared/{api,lib,ui,i18n}/`
- Styling: Tailwind v4 (`src/index.css`)
- Routing: `react-router-dom` **`BrowserRouter`** — **CSR SPA**, bez SSR/SSG
- Public: `public/` (favicons, `.htaccess` za SPA rewrite)

### 2.2 Build / run komande

Iz `SOFTWARE/frontend/package.json`:

| Script | Komanda |
|---|---|
| `dev` | `vite` (port **5174**, proxy `/api` → backend) |
| `build` | `tsc -b && vite build` → `dist/` |
| `preview` | `vite preview` |
| `lint` | `oxlint` |

**Produkcija:** servirati sadržaj `dist/` kao static fajlove. **Node server nije potreban** u produkciji.  
SPA zahteva fallback `/* → index.html` (Apache primer: `public/.htaccess`).

### 2.3 Environment variables (imena — bez vrednosti)

| Ime | Gde | Napomena |
|---|---|---|
| `VITE_API_URL` | build-time (`import.meta.env`) | Default `/api/v1`; u produkciji absolute URL ili same-origin `/api/v1` iza reverse proxy-ja |
| `VITE_PROXY_TARGET` | samo `vite.config.ts` (dev) | Nije deo production build-a |

### 2.4 API URL i auth klijent

- API base: `src/shared/lib/api.ts` → `VITE_API_URL` ili `/api/v1`
- Auth: JWT u **`localStorage`** (`agrotwin.access_token`); header `Authorization: Bearer …`
- **Cookies / session cookie: nisu korišćeni**
- Locale: `localStorage` ključ `agrotwin.locale` (+ headeri `Accept-Language` / `X-Locale`)
- Nema refresh-token toka u frontendu; 401 → logout / `/login`

### 2.5 Uploadovi iz browsera

Multipart (`FormData`) ka API-ju (Bearer): fotografije (`/photos`), soil lab PDF/slike, invoices, knowledge PDF, AI chat attachments, benchmark slike.  
Klijentska kompresija / HEIC: `src/shared/lib/compressImage.ts`.  
Zaštićeni mediji se učitavaju preko `fetch` + blob URL (ne raw `<img src>` na API).

### 2.6 Docker

`SOFTWARE/frontend/Dockerfile` — **development** image (`npm run dev`), **ne** production nginx image.  
Za produkciju: build artifact + static host (kao u `render.yaml`).

---

## 3. Frontend — marketing (`Website/`)

### 3.1 Struktura

- Entry: `src/main.tsx` → `src/App.tsx`
- Sekcije: hero, value, features, pricing, enterprise, how-it-works, faq
- Bez `react-router` — jedna stranica + anchor navigacija
- i18n SR/EN (`src/i18n/`)
- Teški asseti: `public/assets/**`

### 3.2 Build komande

Isti obrazac: `vite` / `tsc -b && vite build` / `vite preview` (dev port **5175**).

### 3.3 Environment variables (imena)

| Ime | Namena |
|---|---|
| `VITE_APP_URL` | CTA → aplikacija (`…/login`) |
| `VITE_SITE_URL` | canonical / OG |
| `VITE_CONTACT_EMAIL` | mailto / footer |
| `VITE_CONTACT_PHONE` | footer |
| `VITE_ENTERPRISE_CONTACT_URL` | opciono POST enterprise forme |

**Nema** autentikacije ni product API klijenta.  
Deploy: čist static hosting / CDN. Nema Dockerfile-a.

---

## 4. Backend (`SOFTWARE/backend`)

### 4.1 Entrypoint

| Mehanizam | Detalj |
|---|---|
| ASGI app | `app/main.py` → `app = create_app()` |
| Docker / PaaS | `Dockerfile` → `CMD ["./scripts/start.sh"]` |
| `start.sh` | `alembic upgrade head` → opcioni seed → opcioni knowledge ingest → `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Passenger (cPanel) | `passenger_wsgi.py` → `a2wsgi.ASGIMiddleware(app)` kao WSGI `application` |
| Compose lokalno | `uvicorn … --reload` na `:8000` (host map `:8001`) |

**Nema** Gunicorn/multi-worker konfiguracije u repou — podrazumevano **jedan** Uvicorn proces.

Lifespan (`app/main.py`): otvara DB, `CatalogService.upsert_defaults()`.

### 4.2 Python dependencies (`requirements.txt`)

Ključni paketi:

| Paket | Uloga |
|---|---|
| `fastapi`, `uvicorn[standard]`, `a2wsgi` | API + server + WSGI bridge |
| `sqlalchemy`, `alembic`, `psycopg[binary]` | ORM + migracije + Postgres |
| `pydantic`, `pydantic-settings`, `email-validator` | config / validacija |
| `PyJWT`, `bcrypt` | auth |
| `python-multipart` | upload |
| `httpx` | outbound HTTP |
| `pypdf`, `pymupdf` | PDF |
| `pillow`, `pytesseract` | slike + OCR |
| `qrcode`, `reportlab` | QR / PDF export |
| `boto3` | S3/R2 |

**Sistemske zavisnosti (Dockerfile):** `libpq-dev`, OpenCV-ish libs, **`tesseract-ocr`** (+ eng/hrv/srp).  
**Nema** Celery/Redis/torch/geopandas u requirements.

### 4.3 PostgreSQL, ORM, migracije

| Stavka | Nalaz |
|---|---|
| ORM | SQLAlchemy 2.x (`app/models/`) |
| Engine | `app/db/session.py`, `pool_pre_ping=True` |
| Connection | `DATABASE_URL` ili `POSTGRES_*`; normalizacija `postgres://` → `postgresql+psycopg://` |
| Migracije | Alembic — `alembic/` + `alembic.ini`; **~43** revision fajla u `alembic/versions/` |
| Auto-migrate | Da — u Docker `scripts/start.sh`. **Ne** — na Passenger startu (ručno) |
| pgvector | Migracija pokušava `CREATE EXTENSION vector`; embedding kolona na knowledge chunks; runtime fallback na JSON cosine ako ekstenzija nedostaje |
| PostGIS | **Nije** u upotrebi (README: namerno) |

Compose image: `pgvector/pgvector:pg16`.

### 4.4 CORS

- Konfig: `CORS_ORIGINS` (comma-separated) → `settings.cors_origin_list`
- `allow_credentials=True`, methods/headers `*`
- U `APP_ENV=development` dodatno regex za localhost/LAN
- U produkciji: **samo** eksplicitne origin vrednosti (mora tačno poklopiti frontend URL-ove, uključujući https)

### 4.5 Authentication / sessions / cookies / security

| Tema | Nalaz |
|---|---|
| Auth | JWT Bearer (`HTTPBearer`), HS256, `SECRET_KEY` |
| Login | `POST {API_PREFIX}/auth/login` |
| Password | bcrypt (`app/core/security.py`) |
| Sessions | **nema** server session store |
| Cookies | **nema** auth cookie |
| Token TTL | `ACCESS_TOKEN_EXPIRE_MINUTES` (default 1440) |
| Roles | `CurrentUser` / `CurrentSuperuser` |
| HTTPS | očekuje se na reverse proxy / PaaS; app ne forsira HSTS |
| Rate limits | in-process (passport, benchmark, outbound spacing) — slabo u multi-instance |
| Public | passport token rute (rate-limited) |
| Docs | `/docs` izložen na ASGI app-u |

### 4.6 Health

- `GET {API_PREFIX}/health` (default `/api/v1/health`) — liveness; **database check je skipped** (namerno radi dugih AI requesta / Render health)
- Root `GET /` pokazuje health path

### 4.7 File storage — upload lokacije, fotografije, fajlovi

**Backendovi:**

- `STORAGE_BACKEND=local` → `STORAGE_LOCAL_PATH` (default `var/storage`)
- `STORAGE_BACKEND=s3` → `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, opcioni `S3_ENDPOINT_URL`, `S3_REGION`
- Bez S3 kredencijala → upozorenje + local fallback

**Tipovi sadržaja:**

| Domen | Tipovi |
|---|---|
| Disease / harvest photos | JPEG/PNG/WebP/GIF |
| Soil lab | PDF + images (+ OCR) |
| AI agronom attachments | images + PDF |
| Knowledge manuals | PDF (`Prirucnici/` ingest na startu) |
| Invoices | PDF + images (limit ~15 MB) |
| Satellite viz | PNG asseti posle sync-a |
| Compliance / passport | generated PDF / QR |

**Rizik:** lokalni disk na ephemeral PaaS (npr. Render free) se briše — **obavezan S3/R2 u produkciji**.

### 4.8 Background jobs / scheduled tasks

**Nema** Celery / APScheduler / Redis queue.

Eksterni cron skriptovi (dokumentovani u headerima):

| Skripta | Namena |
|---|---|
| `scripts/sync_satellite_observations.py` | dnevni Sentinel-2 sync |
| `scripts/run_parcel_intelligence.py` | dnevna parcel intelligence |

Ručni refresh: `POST …/parcels/{id}/satellite/refresh`.  
Orchard “schedules” = farm kalendar u DB, **ne** OS cron.

Bez host cron/worker-a: satelit i intelligence zastarevaju.

### 4.9 Spoljne API integracije

| Integracija | Env / napomena |
|---|---|
| Gemini (OpenAI-compatible) | `AI_*`, `AI_API_KEY` |
| OpenAI fallback / benchmark | `OPENAI_API_KEY`, `AI_OPENAI_*`, `GEMINI_*` (benchmark) |
| Met.no (YR) weather | `YR_USER_AGENT` → locationforecast API |
| SoilGrids (ISRIC) | `SOILGRIDS_*` |
| Copernicus CDSE (STAC/openEO) | `SATELLITE_*`, `COPERNICUS_*` |
| S3 / Cloudflare R2 | `STORAGE_BACKEND=s3`, `S3_*` |
| Email/SMS | **nema** SMTP providera u kodu |

Lokalni AI: `AI_PROVIDER=local` (bez remote LLM).

---

## 5. Environment variables — kompletan katalog (samo imena)

### 5.1 Backend (Settings + ops)

Iz `.env.example` / `app/core/config.py` / start skriptova:

**App / security:**  
`APP_ENV`, `APP_NAME`, `API_PREFIX`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `CORS_ORIGINS`, `PUBLIC_APP_BASE_URL`, `PASSPORT_RATE_LIMIT_PER_MINUTE`

**Database:**  
`DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`

**Storage:**  
`STORAGE_BACKEND`, `STORAGE_LOCAL_PATH`, `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`

**AI agronom:**  
`AI_PROVIDER`, `AI_API_KEY`, `AI_BASE_URL`, `AI_CHAT_MODEL`, `AI_VISION_MODEL`, `AI_EMBEDDING_MODEL`, `AI_EMBEDDING_DIM`, `AI_OPENAI_BASE_URL`, `AI_OPENAI_FALLBACK_MODELS`, `OPENAI_API_KEY`

**Benchmark (server-only):**  
`GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_BASE_URL`, `OPENAI_BENCHMARK_MODEL`, `OPENAI_BENCHMARK_BASE_URL`, `BENCHMARK_TEMPERATURE`, `BENCHMARK_MAX_OUTPUT_TOKENS`, `BENCHMARK_TIMEOUT_SECONDS`, `BENCHMARK_RATE_LIMIT_PER_MINUTE`, `BENCHMARK_GEMINI_INPUT_USD_PER_MTOK`, `BENCHMARK_GEMINI_OUTPUT_USD_PER_MTOK`, `BENCHMARK_OPENAI_INPUT_USD_PER_MTOK`, `BENCHMARK_OPENAI_OUTPUT_USD_PER_MTOK`, `BENCHMARK_MAX_IMAGE_BYTES`, `BENCHMARK_MAX_IMAGE_EDGE`

**Weather / soil:**  
`YR_USER_AGENT`, `SOILGRIDS_BASE_URL`, `SOILGRIDS_USER_AGENT`, `SOILGRIDS_TIMEOUT_SECONDS`, `SOILGRIDS_CACHE_DAYS`, `SOILGRIDS_MIN_INTERVAL_SECONDS`, `SOILGRIDS_MIN_REFRESH_SECONDS`

**Intelligence:**  
`AI_INTELLIGENCE_ENABLED`, `AI_ANALYSIS_MIN_INTERVAL_HOURS`, `AI_INTELLIGENCE_NDVI_CHANGE_THRESHOLD`

**Satellite / Copernicus:**  
`SATELLITE_PROVIDER`, `SATELLITE_ENABLED`, `SATELLITE_LOOKBACK_DAYS`, `SATELLITE_CLOUD_THRESHOLDS`, `SATELLITE_ABSOLUTE_MAX_CLOUD`, `SATELLITE_ZONE_GRID_SIZE`, `SATELLITE_ANOMALY_BELOW_MEAN_FRACTION`, `SATELLITE_ANOMALY_SUDDEN_DECLINE_FRACTION`, `SATELLITE_MIN_INTERVAL_SECONDS`, `SATELLITE_HTTP_TIMEOUT_SECONDS`, `SATELLITE_NDRE_NIR_BAND`, `SATELLITE_NDRE_RED_EDGE_BAND`, `COPERNICUS_STAC_URL`, `COPERNICUS_OPENEO_URL`, `COPERNICUS_USERNAME`, `COPERNICUS_PASSWORD`, `COPERNICUS_CLIENT_ID`, `COPERNICUS_CLIENT_SECRET`, `COPERNICUS_REFRESH_TOKEN`

**Process / ops (ne Settings class):**  
`PORT`, `RUN_SEED` (+ `RENDER_DATABASE_URL` samo u sync helper skripti)

### 5.2 Product frontend

`VITE_API_URL` (+ dev-only `VITE_PROXY_TARGET`)

### 5.3 Marketing Website

`VITE_APP_URL`, `VITE_SITE_URL`, `VITE_CONTACT_EMAIL`, `VITE_CONTACT_PHONE`, `VITE_ENTERPRISE_CONTACT_URL`

### 5.4 Compose root (`SOFTWARE/.env.example`)

`SECRET_KEY`, `POSTGRES_*`, `CORS_ORIGINS`, `VITE_API_URL`, `YR_USER_AGENT`, `SOILGRIDS_*`

---

## 6. Postojeći deploy artefakti

| Artefakt | Sadržaj |
|---|---|
| `render.yaml` | Postgres + Docker API + static frontend; health `/api/v1/health`; AI/S3 env keys |
| `SOFTWARE/docs/DEPLOY_RENDER.md` | Render procedura |
| `SOFTWARE/docs/DEPLOY_PRODUCTION.md` | SuperHosting napomene (frontend FTPS; API često nije izvodljiv) |
| `SOFTWARE/backend/passenger_wsgi.py` | cPanel Python App entry |
| `SOFTWARE/frontend/public/.htaccess` | SPA rewrite |

---

## 7. Shared hosting — problematične zavisnosti

### 7.1 Šta puca / je nepouzdano na PHP/shared hostingu

1. **Runtime** — nije PHP; FastAPI treba trajni Python ASGI/WSGI worker  
2. **PostgreSQL + pgvector** — shared planovi često nude samo MySQL; vector extension zahteva admin  
3. **Sistemski binarni** — Tesseract + lang packovi, libpq, PyMuPDF native libs  
4. **Ephemeral / mali disk** — `var/storage` gubi uploadove i PDF priručnike  
5. **Dugi outbound requesti** — AI cascade, SoilGrids (~90s), Copernicus (~120s); worker kill / timeout  
6. **Cron** — satelit + intelligence skripte moraju u istom venv-u; često nema pouzdanog cron-a  
7. **Passenger bez `start.sh`** — Alembic se ne pokreće automatski  
8. **Memorija** — PDF OCR, rasterizacija, satelitski PNG; rizik OOM  
9. **In-process rate limit / circuit breaker** — reset na svaki recycle workera  
10. **Multi-instance horizontal scale** — bez shared redis/queue rate limiti i lockovi nisu konzistentni  

### 7.2 Šta može na shared / static

| Deo | Shared/static |
|---|---|
| `Website/` marketing | Da (Apache/nginx/CDN) |
| `SOFTWARE/frontend` `dist/` | Da, uz SPA rewrite + ispravan `VITE_API_URL` / proxy |
| API FastAPI | Samo ako host eksplicitno podržava Python + Postgres + duge requeste (i dalje ograničeno) |

### 7.3 Šta zahteva zaseban server / cloud servis

| Potreba | Preporučeni tip |
|---|---|
| API proces | Docker web service / VPS / Render/Fly/Railway |
| PostgreSQL (+ vector) | Managed Postgres (Render, RDS, Neon, …) |
| Object storage | Cloudflare R2 / AWS S3 / MinIO |
| LLM | Gemini / OpenAI API keys (eksterni SaaS) |
| Satellite | Copernicus CDSE credentials + outbound HTTPS |
| Weather / SoilGrids | Outbound HTTPS + validan User-Agent |
| Daily jobs | Cron na VPS, Render Cron Job, GitHub Actions, ili worker container |
| Marketing / app static | CDN ili static site host |

---

## 8. Konkretni nalazi (checklist)

### Positivno / već spremno

- [x] Dockerized API sa migracijama na startu  
- [x] Render blueprint za full stack  
- [x] JWT auth bez cookie kompleksnosti (lako za static SPA)  
- [x] S3 storage adapter već postoji  
- [x] Health endpoint za PaaS  
- [x] Frontend SPA build + `.htaccess`  
- [x] Marketing odvojen od app-a  
- [x] pgvector graceful degradation  

### Rizici / rupe

- [ ] Local storage default u `render.yaml` (`STORAGE_BACKEND=local`) — **opasno** za trajnost fajlova  
- [ ] Nema ugrađenog job runnera — cron mora biti eksplicitno podešen  
- [ ] Health ne proverava DB — false green moguć  
- [ ] `/docs` javno u produkciji  
- [ ] Single Uvicorn worker — concurrency limitiran  
- [ ] CORS mora tačno uključiti sve frontend origine (marketing + app)  
- [ ] `VITE_*` se peče u build — promena API URL zahteva rebuild frontenda  
- [ ] Demo seed (`RUN_SEED`) mora ostati `false` u produkciji  
- [ ] Copernicus openEO auth je osetljiv (username/password vs client credentials)  
- [ ] Passenger putanja: ručne migracije + slab fit za AI/OCR/satelit  

---

## 9. Preporučena procedura migracije na produkciju

### Faza A — infrastruktura

1. Provision **managed PostgreSQL 16** (poželjno sa pravom `CREATE EXTENSION vector`).  
2. Provision **object storage** (R2/S3) + bucket + access keys.  
3. Provision **API host** (Docker): image iz `SOFTWARE/backend/Dockerfile`, context `SOFTWARE/backend`.  
4. Provision **static hosts**:
   - App UI: build `SOFTWARE/frontend`
   - Marketing: build `Website/`
5. DNS: npr. `app.*` → app static; apex/www → marketing; `api.*` → API (ili reverse proxy `/api`).

### Faza B — tajne i env (API)

1. Generiši jak `SECRET_KEY` (≥32).  
2. Postavi `APP_ENV=production`, `API_PREFIX=/api/v1`.  
3. Postavi `DATABASE_URL` (ili `POSTGRES_*`).  
4. Postavi `CORS_ORIGINS` na **sve** production frontend URL-ove (app + marketing ako zove API).  
5. Postavi `PUBLIC_APP_BASE_URL` na app origin.  
6. `STORAGE_BACKEND=s3` + svi `S3_*`.  
7. AI: `AI_PROVIDER`, `AI_API_KEY`, modeli, opcioni `OPENAI_API_KEY` za fallback.  
8. `YR_USER_AGENT`, `SOILGRIDS_USER_AGENT` sa validnim kontaktom.  
9. Ako satelit treba u produkciji: `SATELLITE_ENABLED=true` + `COPERNICUS_*`.  
10. `RUN_SEED=false`.  

### Faza C — baza

1. Prvi deploy API-ja pokreće `alembic upgrade head` preko `start.sh`.  
2. Verifikuj ekstenziju `vector` (opciono, ali poželjno za RAG).  
3. **Ne** seed-uj demo admina u produkciji; kreiraj pravi superuser kroz kontrolisan proces.  
4. Ako postoje knowledge PDF-ovi: osiguraj ingest (`Prirucnici/` u image ili S3 + `ingest_knowledge.py`).

### Faza D — frontendi

1. Build app:
   ```bash
   cd SOFTWARE/frontend
   # VITE_API_URL=https://<api-host>/api/v1   # ili /api/v1 ako same-origin proxy
   npm ci && npm run build
   ```
2. Deploy `dist/` + SPA fallback.  
3. Build marketing:
   ```bash
   cd Website
   # VITE_APP_URL / VITE_SITE_URL / contact vars
   npm ci && npm run build
   ```
4. Deploy `Website/dist/`.  
5. Proveri CORS: login iz app origin-a radi.

### Faza E — cron / jobs

Na scheduler-u (isti env kao API):

```cron
# primer — prilagoditi putanje/venv
15 4 * * *  cd /app && python scripts/sync_satellite_observations.py
30 5 * * *  cd /app && python scripts/run_parcel_intelligence.py
```

Bez ovoga satelit/intelligence ostaju samo na manuelni refresh.

### Faza F — smoke test

1. `GET /api/v1/health` → 200  
2. `POST /api/v1/auth/login` → JWT  
3. Upload male slike / PDF → fajl vidljiv posle restart API instance (potvrda S3)  
4. AI chat (ako keys postavljeni)  
5. SPA deep link (`/orchard/...`) ne daje 404  
6. Marketing CTA vodi na `…/login`  
7. Passport public URL (ako se koristi)  
8. Logs: nema crash na Alembic; nema write na ephemeral disk kao primary storage  

### Faza G — hardening (preporučeno posle go-live)

- Zatvoriti ili zaštititi `/docs` u produkciji  
- Multi-worker (Gunicorn+Uvicorn) samo uz shared rate-limit strategiju  
- Backup Postgres + S3 lifecycle  
- Monitoring timeouta (AI/satellite)  
- Rotacija `SECRET_KEY` / API keys procedura  

---

## 10. Minimalni produkcioni “shape”

```
[ CDN / Static ]  Website + App SPA
        │
        ▼
[ Reverse proxy / TLS ]
        │
        ▼
[ Docker: FastAPI + Uvicorn + Tesseract ]
        ├─ Alembic on boot
        ├─ Managed PostgreSQL (+ vector)
        ├─ S3/R2 durable storage
        ├─ Cron: satellite + intelligence
        └─ Outbound: Gemini/OpenAI, Met.no, SoilGrids, Copernicus
```

**Ne preporučuje se:** “sve na jednom jeftinom PHP shared hostingu”.  
**Prihvatljiv hibrid:** static frontend(i) na shared/CDN + API+DB+storage+cron na cloud/VPS (već dokumentovano u `SOFTWARE/docs/DEPLOY_PRODUCTION.md`).

---

## 11. Referentni fajlovi

| Tema | Putanja |
|---|---|
| API app | `SOFTWARE/backend/app/main.py` |
| Settings | `SOFTWARE/backend/app/core/config.py` |
| Env template | `SOFTWARE/backend/.env.example` |
| Start / migrate | `SOFTWARE/backend/scripts/start.sh` |
| Dockerfile | `SOFTWARE/backend/Dockerfile` |
| Passenger | `SOFTWARE/backend/passenger_wsgi.py` |
| Auth | `SOFTWARE/backend/app/core/security.py`, `app/api/routes/auth.py`, `app/api/deps.py` |
| Storage | `SOFTWARE/backend/app/storage/` |
| Cron scripts | `SOFTWARE/backend/scripts/sync_satellite_observations.py`, `run_parcel_intelligence.py` |
| Compose | `SOFTWARE/docker-compose.yml` |
| Render | `render.yaml` |
| App frontend API/auth | `SOFTWARE/frontend/src/shared/lib/api.ts`, `auth.ts` |
| App SPA Apache | `SOFTWARE/frontend/public/.htaccess` |
| Marketing config | `Website/src/lib/config.ts`, `Website/.env.example` |
| Postojeći deploy docs | `SOFTWARE/docs/DEPLOY_RENDER.md`, `DEPLOY_PRODUCTION.md` |

---

*Ovaj dokument je audit nalaz. Ne menja runtime ponašanje projekta.*
