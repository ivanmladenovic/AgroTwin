from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "app_error") -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resurs nije pronađen") -> None:
        super().__init__(message, status_code=404, code="not_found")


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Niste prijavljeni") -> None:
        super().__init__(message, status_code=401, code="unauthorized")


class ForbiddenError(AppError):
    def __init__(self, message: str = "Nije dozvoljeno") -> None:
        super().__init__(message, status_code=403, code="forbidden")


def _cors_headers(request: Request) -> dict[str, str]:
    origin = request.headers.get("origin")
    if not origin:
        return {}
    allowed = get_settings().cors_origin_list
    if origin not in allowed:
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
            headers=_cors_headers(request),
        )

    @app.exception_handler(FileNotFoundError)
    async def missing_file_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Datoteka nije pronađena na serveru. Otpremite je ponovo.",
                "code": "storage_missing",
            },
            headers=_cors_headers(request),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Interna greška servera", "code": "server_error"},
            headers=_cors_headers(request),
        )
