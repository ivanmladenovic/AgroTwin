from fastapi import APIRouter

from app.api.routes import activities, ai, auth, catalogs, costs, dashboard, diseases, farms, harvests, health, invoices, knowledge, parcels, weather

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(farms.router)
api_router.include_router(parcels.router)
api_router.include_router(harvests.router)
api_router.include_router(weather.router)
api_router.include_router(catalogs.router)
api_router.include_router(activities.router)
api_router.include_router(costs.router)
api_router.include_router(invoices.router)
api_router.include_router(diseases.router)
api_router.include_router(knowledge.router)
api_router.include_router(ai.router)
