from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


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


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )
