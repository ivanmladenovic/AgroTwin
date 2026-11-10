"""Request locale (sr | en) and reply-language selection for agronomist chat."""

from __future__ import annotations

import re
from typing import Literal

AppLocale = Literal["sr", "en"]

_SR_DIACRITICS = frozenset("čćđšžČĆĐŠŽ")
_LATIN_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ']+")

_ENGLISH_HINTS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "should",
        "could",
        "can",
        "may",
        "might",
        "what",
        "when",
        "where",
        "why",
        "how",
        "which",
        "who",
        "my",
        "your",
        "our",
        "their",
        "this",
        "that",
        "these",
        "those",
        "with",
        "without",
        "for",
        "from",
        "about",
        "please",
        "thanks",
        "thank",
        "hello",
        "hi",
        "yes",
        "no",
        "not",
        "orchard",
        "hazelnut",
        "hazel",
        "farm",
        "field",
        "parcel",
        "soil",
        "fertilizer",
        "fertilisation",
        "fertilization",
        "irrigation",
        "water",
        "disease",
        "pest",
        "yield",
        "harvest",
        "plant",
        "tree",
        "trees",
        "recommend",
        "advice",
        "help",
        "analyze",
        "analysis",
        "photo",
        "image",
        "document",
    }
)

_SR_HINTS = frozenset(
    {
        "da",
        "ne",
        "je",
        "su",
        "sam",
        "si",
        "smo",
        "ste",
        "sam",
        "sta",
        "šta",
        "kako",
        "kada",
        "gde",
        "zasto",
        "zašto",
        "molim",
        "hvala",
        "leska",
        "lesnik",
        "voćnjak",
        "vocnjak",
        "parcela",
        "gazdinstvo",
        "đubrenje",
        "djubrenje",
        "dubrenje",
        "navodnjavanje",
        "berba",
        "prinos",
        "analiza",
        "zemljiste",
        "zemljište",
        "pomoc",
        "pomoć",
        "hajde",
        "moze",
        "može",
        "treba",
        "imam",
        "moj",
        "moja",
        "moje",
    }
)

REPLY_LANGUAGE_INSTRUCTION_EN = (
    "LANGUAGE: Write your entire reply in English (Latin script). "
    "Keep cultivar names in their original form. Use plain text without Markdown."
)


def normalize_app_locale(value: str | None) -> AppLocale:
    if not value:
        return "sr"
    token = value.strip().lower().split("-")[0].split("_")[0]
    if token.startswith("en"):
        return "en"
    if token.startswith("sr"):
        return "sr"
    return "sr"


def parse_request_locale(
    accept_language: str | None,
    x_locale: str | None,
) -> AppLocale:
    """Prefer explicit X-Locale, then the first Accept-Language tag. Default sr."""
    if x_locale and x_locale.strip():
        return normalize_app_locale(x_locale)
    if accept_language and accept_language.strip():
        first = accept_language.split(",")[0].strip()
        tag = first.split(";")[0].strip()
        return normalize_app_locale(tag)
    return "sr"


def is_text_likely_english(text: str) -> bool:
    """Heuristic: Latin script without Serbian diacritics and/or common English words."""
    if not text or not text.strip():
        return False
    if any(ch in text for ch in _SR_DIACRITICS):
        return False
    words = [w.lower() for w in _LATIN_WORD.findall(text)]
    if not words:
        return False
    en_hits = sum(1 for w in words if w in _ENGLISH_HINTS)
    sr_hits = sum(1 for w in words if w in _SR_HINTS)
    if en_hits >= 2 and en_hits > sr_hits:
        return True
    if len(words) >= 4 and en_hits >= 1 and sr_hits == 0:
        return True
    return False


def effective_reply_locale(request_locale: AppLocale, user_text: str) -> AppLocale:
    if request_locale == "en":
        return "en"
    if is_text_likely_english(user_text):
        return "en"
    return "sr"
