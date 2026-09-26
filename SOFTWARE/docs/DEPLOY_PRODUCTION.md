# Production deploy — SuperHosting (agrotwin.srpskisafran.rs)

After you push to `main`, GitHub Actions builds the frontend and uploads:

- Frontend (static) → FTP account root  
- Backend (Python) → `./api/`

## GitHub secrets (already set)

- `FTP_SERVER` — hostname only, no `ftps://`
- `FTP_USERNAME`
- `FTP_PASSWORD`

## One-time SuperHosting setup

### 1. PostgreSQL

In cPanel create a PostgreSQL database + user. Note host, name, user, password.

### 2. Python App (cPanel → Setup Python App)

| Field | Value |
| --- | --- |
| Python version | 3.12 if available (else newest 3.x) |
| Application root | `agrotwin.srpskisafran.rs/api` (path that contains `passenger_wsgi.py`) |
| Application URL | `/api` |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |

Click **Run Pip Install** (uses `requirements.txt`).

### 3. Environment variables (Python App)

```bash
APP_ENV=production
SECRET_KEY=<long-random-secret-at-least-32-chars>
API_PREFIX=/v1
CORS_ORIGINS=https://agrotwin.srpskisafran.rs
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
STORAGE_BACKEND=local
STORAGE_LOCAL_PATH=var/storage
```

Optional AI / soil keys as needed (`GEMINI_API_KEY`, `OPENAI_API_KEY`, …).

`API_PREFIX=/v1` + Application URL `/api` → public API base  
`https://agrotwin.srpskisafran.rs/api/v1` (matches the frontend build).

### 4. Database migrations (first time + after schema changes)

SSH into the account (if enabled), then:

```bash
cd ~/agrotwin.srpskisafran.rs/api   # adjust to your real path
source /home/USER/virtualenv/.../bin/activate   # path shown in Python App UI
alembic upgrade head
python scripts/seed.py   # only for initial demo data; skip on real prod if undesired
```

If SSH is not available, ask SuperHosting support how to run a one-off command in the Python App environment, or enable SSH.

### 5. Restart the Python App

In cPanel Python App → **Stop** → **Start** (or Restart) after env / dependency changes.

### 6. Verify

- https://agrotwin.srpskisafran.rs — login UI  
- https://agrotwin.srpskisafran.rs/api/v1/health — API health  

## Automatic flow

```
git push origin main
        ↓
GitHub Actions
        ↓
Vite build (VITE_API_URL=https://agrotwin.srpskisafran.rs/api/v1)
        ↓
FTPS → frontend files + ./api backend code
```

You do **not** need extra secrets for `FTP_SERVER_DIR` or `VITE_API_URL`.

## Limits of FTPS-only hosting

Uploading files is automatic. Starting Passenger, installing new pip packages after `requirements.txt` changes, and running Alembic still need a one-time/occasional cPanel (or SSH) action. After the Python App exists, most code pushes only need the FTPS sync; restart the app if Passenger does not reload.
