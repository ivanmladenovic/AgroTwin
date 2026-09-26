from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

MAX_EDGE = 1600
JPEG_QUALITY = 72


@dataclass(frozen=True)
class CompressedImage:
    content: bytes
    content_type: str
    filename: str
    extension: str


def compress_photo(content: bytes, filename: str = "photo.jpg") -> CompressedImage:
    """Downscale and JPEG-encode a photo for cheap storage.

    Falls back to the original bytes if the file is not a readable image or
    compression would not shrink an already-small JPEG.
    """
    stem = Path(filename).stem or "photo"
    original = CompressedImage(
        content=content,
        content_type=_guess_content_type(content, filename),
        filename=filename,
        extension=_extension_for(filename, content),
    )
    if not content:
        return original

    try:
        with Image.open(BytesIO(content)) as opened:
            opened.load()
            image = ImageOps.exif_transpose(opened) or opened
            image = _to_rgb(image)
            width, height = image.size
            longest = max(width, height)
            if longest > MAX_EDGE:
                scale = MAX_EDGE / longest
                image = image.resize(
                    (max(1, round(width * scale)), max(1, round(height * scale))),
                    Image.Resampling.BILINEAR,
                )
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=False)
            compressed = buffer.getvalue()
    except Exception:
        return original

    if not compressed or len(compressed) >= len(content):
        return original
    return CompressedImage(
        content=compressed,
        content_type="image/jpeg",
        filename=f"{stem}.jpg",
        extension=".jpg",
    )


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if image.mode in {"RGBA", "LA", "P"}:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _guess_content_type(content: bytes, filename: str) -> str:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        return "image/gif"
    suffix = Path(filename).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "application/octet-stream")


def _extension_for(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".jpeg":
        return ".jpg"
    if suffix in {".jpg", ".png", ".webp", ".gif"}:
        return suffix
    guessed = _guess_content_type(content, filename)
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(guessed, ".bin")
