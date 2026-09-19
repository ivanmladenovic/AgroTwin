# AgroTwin

Digital orchard management platform, starting with hazelnut orchards.

Phase 0 is the production-quality foundation: project structure, domain model, database migrations, a seeded development user, and a working frontend that talks to the API.

Phase 1 generates rectangular orchards as real rows and trees (Digital Twin).

Phase 2 and 3 add the orchard journal, tree journal, configurable activities, and cost tracking. Activities describe what happened; cost items describe how much it cost. Totals are calculated from line items and are never stored.

## Architecture

```
SOFTWARE/
  frontend/          React + TypeScript (Vite)
  backend/           FastAPI + SQLAlchemy 2 + Alembic
  docker-compose.yml PostgreSQL, API and frontend
```

**Frontend** uses a feature-based layout (`features/auth`, `features/farms`, `features/dashboard`) with shared UI primitives under `shared/ui`.

**Backend** keeps HTTP, validation, business logic and data access separate:

- `app/api` routes and dependencies
- `app/schemas` Pydantic request/response models
- `app/services` application logic
- `app/repositories` data access
- `app/models` SQLAlchemy domain model
- `app/core` configuration, security and errors

### Domain hierarchy

```
User → Farm → Parcel → Row → Tree
```

Activities and costs are **scoped**. A record can belong to a farm, a parcel, a row or a single tree. Parent identifiers are stored on the same row so later reporting can total costs per orchard, parcel, row, tree, hectare or period without walking the tree.

Latitude and longitude columns exist on farm, parcel and tree. PostGIS is intentionally not introduced in Phase 0.

## Local development

Development ports default to **5433** (Postgres), **8001** (API) and **5174** (frontend) so they do not collide with other local services.

### 1. Environment

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### 2. Start PostgreSQL

```bash
docker compose up -d db
```

### 3. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8001
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5174](http://localhost:5174).

Demo user (seeded automatically):

- email: `demo@agrotwin.com`
- password: `demo12345`

### Full stack with Docker

```bash
docker compose up --build
```

Then run migrations and seed against the database:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/seed.py
```

## API

- `GET /api/v1/health` — API and database check
- `POST /api/v1/auth/login` — JWT for the development user
- `GET /api/v1/auth/me` — current user
- `GET /api/v1/farms` — farms owned by the current user
- `GET /api/v1/activity-types` — configurable activity types
- `GET /api/v1/cost-categories` — configurable cost categories
- `GET /api/v1/activities` — orchard journal with filters
- `POST /api/v1/activities` — create an activity (parcel, row or tree scope)
- `POST /api/v1/activities/{id}/costs` — add a cost item to an activity
- `GET /api/v1/costs/summary` — totals by period, category, activity type, tree and hectare
- `GET /api/v1/activities/export.csv` — CSV export of activities
- `GET /api/v1/costs/export.csv` — CSV export of cost items
- `GET /api/v1/parcels/{id}/trees/{treeId}/journal` — tree journal timeline

Interactive docs: [http://localhost:8001/docs](http://localhost:8001/docs)

## Phase 0 scope

Included:

- typed backend and frontend foundations
- complete domain tables for later features
- JWT auth architecture with a seeded development user
- Docker development environment
- dashboard that verifies API, database and seed data

Not included (intentionally):

- GIS / PostGIS
- knowledge base and AI chat
- drone imagery
- multi-tenant organisations and production auth flows
