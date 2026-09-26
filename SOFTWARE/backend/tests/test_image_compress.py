from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest import TestCase
import os
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from PIL import Image

from app.storage.images import MAX_EDGE, compress_photo


class PhotoCompressionTests(TestCase):
    def test_large_photo_becomes_small_jpeg(self) -> None:
        original = _noisy_jpeg(2400, 1800, quality=95)
        result = compress_photo(original, "simptom.jpg")
        self.assertEqual(result.content_type, "image/jpeg")
        self.assertEqual(result.extension, ".jpg")
        self.assertTrue(result.content.startswith(b"\xff\xd8"))
        self.assertLess(len(result.content), len(original) // 2)
        with Image.open(BytesIO(result.content)) as image:
            self.assertLessEqual(max(image.size), MAX_EDGE)

    def test_small_jpeg_is_not_inflated(self) -> None:
        original = _noisy_jpeg(400, 300, quality=40)
        result = compress_photo(original, "mala.jpg")
        self.assertEqual(result.content_type, "image/jpeg")
        self.assertLessEqual(len(result.content), len(original))

    def test_unreadable_bytes_are_kept(self) -> None:
        payload = b"not-an-image"
        result = compress_photo(payload, "notes.bin")
        self.assertEqual(result.content, payload)


def _noisy_jpeg(width: int, height: int, quality: int) -> bytes:
    image = Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()
