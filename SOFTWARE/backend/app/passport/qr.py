from __future__ import annotations

import io

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def generate_qr_png(url: str, *, box_size: int = 8, border: int = 2) -> bytes:
    """Generate a QR PNG for the public passport URL (no external API)."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
