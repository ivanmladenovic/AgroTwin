"""WSGI entrypoint for SuperHosting cPanel "Setup Python App" (Passenger).

Configure once in cPanel:
  Application root → folder that contains this file (e.g. .../api)
  Application URL  → /api
  Application startup file → passenger_wsgi.py
  Application entry point → application

Set environment in cPanel (Python App → Environment variables), for example:
  SECRET_KEY=...
  APP_ENV=production
  API_PREFIX=/v1
  CORS_ORIGINS=https://agrotwin.srpskisafran.rs
  DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/DBNAME
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from a2wsgi import ASGIMiddleware

from app.main import app

application = ASGIMiddleware(app)
