from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.benchmark.types import BenchmarkImage
from app.core.config import Settings
from app.core.exceptions import AppError

ALLOWED_MIME = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}


def normalize_mime(mime_type: str | None, filename: str = "") -> str:
    mime = (mime_type or "").split(";")[0].strip().lower()
    if mime == "image/jpg":
        mime = "image/jpeg"
    if mime in ALLOWED_MIME:
        return "image/jpeg" if mime == "image/jpg" else mime
    lower = filename.lower()
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    raise AppError(
        "Prihvataju se samo JPEG, PNG i WebP slike",
        status_code=422,
        code="invalid_image",
    )


def validate_benchmark_image(
    content: bytes,
    *,
    mime_type: str | None,
    filename: str,
    settings: Settings,
    source: str = "upload",
) -> BenchmarkImage:
    if not content:
        raise AppError("Slika je prazna", status_code=422, code="invalid_image")
    if len(content) > settings.benchmark_max_image_bytes:
        mb = settings.benchmark_max_image_bytes // (1024 * 1024)
        raise AppError(
            f"Slika je veća od {mb} MB",
            status_code=422,
            code="image_too_large",
        )
    mime = normalize_mime(mime_type, filename)
    try:
        with Image.open(BytesIO(content)) as opened:
            opened.load()
            width, height = opened.size
    except Exception as exc:
        raise AppError(
            "Fajl nije čitljiva slika",
            status_code=422,
            code="invalid_image",
        ) from exc
    longest = max(width, height)
    if longest > settings.benchmark_max_image_edge:
        raise AppError(
            f"Dimenzije slike ({width}×{height}) prelaze limit od "
            f"{settings.benchmark_max_image_edge} px na dužoj ivici",
            status_code=422,
            code="image_too_large",
        )
    if width < 16 or height < 16:
        raise AppError(
            "Slika je premala za analizu",
            status_code=422,
            code="invalid_image",
        )
    return BenchmarkImage(
        content=content,
        mime_type=mime,
        filename=filename or "image.jpg",
        width=width,
        height=height,
        source=source,
    )
