# Deploy AgroTwin on Render (full stack)

SuperHosting shared hosting cannot run FastAPI. Use Render for:

- PostgreSQL database
- FastAPI backend (`agrotwin-api`)
- React frontend (`agrotwin-web`)

Repo already includes `render.yaml` at the project root.

---

## Korak 0 — Šta ti treba

1. Nalog na [https://render.com](https://render.com) (GitHub login)
2. GitHub repo `ivanmladenovic/AgroTwin` (već imaš, kod je na `main`)
3. ~15–20 minuta

Napomena: Render free Postgres/web može da “zaspi” posle neaktivnosti (prvi request sporiji). Za stalni rad kasnije uzmi plaćeni plan.

---

## Korak 1 — Poveži GitHub sa Renderom

1. Otvori [https://dashboard.render.com](https://dashboard.render.com)
2. Uloguj se preko **GitHub**
3. Dozvoli Render-u pristup repo-u **AgroTwin** (All repositories ili samo taj)

---

## Korak 2 — Deploy Blueprint (sve odjednom)

1. Dashboard → **New** → **Blueprint**
2. Izaberi repo **AgroTwin**
3. Branch: **main**
4. Render treba da nađe fajl `render.yaml`
5. Klikni **Apply** / **Create resources**

Kreiraće:
- `agrotwin-db` (Postgres)
- `agrotwin-api` (Docker / FastAPI)
- `agrotwin-web` (static frontend)

Sačekaj da **agrotwin-api** status bude **Live** (prvi build 5–10 min).

---

## Korak 3 — Proveri API

1. Dashboard → **agrotwin-api** → kopiraj URL  
   Primer: `https://agrotwin-api.onrender.com`
2. Otvori u browseru:

```text
https://agrotwin-api.onrender.com/api/v1/health
```

Treba JSON tipa:

```json
{"status":"ok","service":"AgroTwin","database":"connected"}
```

Ako padne: **Logs** tab → pošalji grešku.

---

## Korak 4 — Podesi frontend da zna API URL

1. Dashboard → **agrotwin-web** → **Environment**
2. Proveri / postavi:

```text
VITE_API_URL=https://agrotwin-api.onrender.com/api/v1
```

(Zameni tačnim API URL-om iz koraka 3.)

3. **Manual Deploy** → **Clear build cache & deploy**  
   (bitno: `VITE_*` ulazi u build, mora se ponovo buildovati)

---

## Korak 5 — Podesi CORS na API-ju

1. Dashboard → **agrotwin-api** → **Environment**
2. `CORS_ORIGINS` postavi na frontend URL (i SuperHosting ako ga još koristiš):

```text
https://agrotwin-web.onrender.com,https://agrotwin.srpskisafran.rs
```

3. Sačuvaj → sačeka restart servisa.

---

## AI Agronom (Gemini first)

On **agrotwin-api** set:

```text
AI_PROVIDER=openai_compatible
AI_API_KEY=<your Gemini API key>
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
AI_CHAT_MODEL=gemini-3.8-flash
AI_VISION_MODEL=gemini-3.8-flash
AI_EMBEDDING_MODEL=gemini-embedding-001
AI_EMBEDDING_DIM=1536
```

`AI_API_KEY` must be set manually in the Render dashboard (Blueprint marks it `sync: false`).

To switch later to GPT-5, change base URL/models and use the OpenAI key.

Blueprint ima `RUN_SEED=true` za prvi start.

Posle uspešnog seed-a **isključi seed** da se ne ponavlja:

1. **agrotwin-api** → Environment  
2. `RUN_SEED` → `false`  
3. Redeploy / sačuvaj

Login:

- email: `admin@agrotwin.rs`
- password: the value configured for production (not the old demo `admin`)

**Odmah promeni lozinku** na produkciji kad budeš mogao.

---

## Korak 7 — Otvori aplikaciju

1. Dashboard → **agrotwin-web** → otvori URL  
   Primer: `https://agrotwin-web.onrender.com`
2. Prijavi se demo nalogom

---

## Korak 8 (opciono) — Custom domen `agrotwin.srpskisafran.rs`

### Frontend na Render
1. **agrotwin-web** → **Settings** → **Custom Domains** → dodaj `agrotwin.srpskisafran.rs`
2. Kod SuperHostinga / DNS: CNAME (ili A) kako Render kaže
3. Update `CORS_ORIGINS` i `VITE_API_URL` ako API ima svoj domen

### API domen (opciono)
npr. `api.agrotwin.srpskisafran.rs` → **agrotwin-api** Custom Domain

---

## Posle toga — automatski deploy

Svaki `git push` na `main` Render sam rebuild-uje servise povezane na taj repo.

SuperHosting FTPS workflow više nije potreban za platformu (možeš ga ostaviti ili ugasiti u GitHub Actions).

---

## Česte greške

| Problem | Rešenje |
| --- | --- |
| Frontend radi, login ne | Pogrešan `VITE_API_URL` ili nije Clear cache redeploy |
| CORS error u browseru | Dodaj tačan frontend origin u `CORS_ORIGINS` |
| DB connection error | Sačekaj da Postgres bude Ready; proveri `DATABASE_URL` |
| API “spava” (spor prvi request) | Free tier spin-down — normalno |
| Seed ponovo brše podatke | `RUN_SEED=false` |

---

## Env vars (pregled)

**agrotwin-api**
- `SECRET_KEY` (auto)
- `DATABASE_URL` (iz Postgres)
- `CORS_ORIGINS`
- `APP_ENV=production`
- `API_PREFIX=/api/v1`
- `RUN_SEED=true` samo prvi put
- opciono: `GEMINI_API_KEY`, `OPENAI_API_KEY`, …

**agrotwin-web**
- `VITE_API_URL=https://<api-service>.onrender.com/api/v1`
