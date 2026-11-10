from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError


class PublicPassportRateLimiter:
    """In-process IP rate limit for anonymous passport reads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client_key: str, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        limit = max(1, getattr(settings, "passport_rate_limit_per_minute", 60))
        window = 60.0
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[client_key]
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if len(bucket) >= limit:
                raise AppError(
                    "Previše zahteva za pasoš. Sačekajte trenutak.",
                    status_code=429,
                    code="passport_rate_limited",
                )
            bucket.append(now)


passport_rate_limiter = PublicPassportRateLimiter()
