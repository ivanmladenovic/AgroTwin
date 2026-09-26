from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from uuid import UUID

from app.core.config import Settings
from app.core.exceptions import AppError


class BenchmarkRateLimiter:
    """Simple in-process per-user rate limit for the developer benchmark endpoint."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, user_id: UUID, settings: Settings) -> None:
        limit = max(1, settings.benchmark_rate_limit_per_minute)
        window = 60.0
        key = str(user_id)
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if len(bucket) >= limit:
                raise AppError(
                    f"Previše benchmark zahteva. Sačekajte trenutak (limit {limit}/min).",
                    status_code=429,
                    code="benchmark_rate_limited",
                )
            bucket.append(now)


rate_limiter = BenchmarkRateLimiter()
