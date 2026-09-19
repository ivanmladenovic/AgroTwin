from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from io import BytesIO

PARSER_VERSION = "agrotwin-kb-1.0"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def tesseract_version() -> str:
    if not tesseract_available():
        return ""
    try:
        result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, check=False)
        line = (result.stdout or result.stderr or "").splitlines()
        return line[0].strip() if line else "tesseract"
    except OSError:
        return "tesseract"


def tesseract_languages() -> set[str]:
    if not tesseract_available():
        return set()
    try:
        result = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, check=False)
        return {line.strip() for line in (result.stdout or "").splitlines() if line.strip() and " " not in line}
    except OSError:
        return set()


_OCR_LANG: str | None = None


def choose_ocr_lang() -> str:
    global _OCR_LANG
    if _OCR_LANG:
        return _OCR_LANG
    langs = tesseract_languages()
    if "srp_latn" in langs and "eng" in langs:
        _OCR_LANG = "srp_latn+eng"
    elif "srp_latn" in langs:
        _OCR_LANG = "srp_latn"
    elif "srp" in langs and "eng" in langs:
        _OCR_LANG = "srp+eng"
    elif "eng" in langs:
        _OCR_LANG = "eng"
    else:
        _OCR_LANG = "eng"
    return _OCR_LANG


def ocr_png(content: bytes, lang: str | None = None) -> str:
    if not tesseract_available():
        raise RuntimeError("Tesseract OCR nije instaliran")
    from PIL import Image
    import pytesseract

    image = Image.open(BytesIO(content))
    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    config = "--oem 1 --psm 6"
    text = pytesseract.image_to_string(image, lang=lang or choose_ocr_lang(), config=config)
    return text.strip()


def normalize_ocr_text(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    replacements = {
        "djubrivo": "đubrivo",
        "djubrenje": "đubrenje",
        "leška": "leska",
        "lesnik": "lešnik",
        "susnezica": "sušnežica",
    }
    lowered = text
    for src, dst in replacements.items():
        lowered = re.sub(src, dst, lowered, flags=re.IGNORECASE)
    return lowered.strip()
