from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401
from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.session import SessionLocal
from app.services.catalog import CatalogService


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db = SessionLocal()
    try:
        CatalogService(db).upsert_defaults()
        db.commit()
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Platforma za upravljanje voćnjakom lesnika.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)
    application.include_router(api_router, prefix=settings.api_prefix)
    return application


app = create_app()
