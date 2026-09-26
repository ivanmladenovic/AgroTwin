from __future__ import annotations

import threading
import time


class SoilGridsRateLimiter:
    """Process-wide fair-use gate. SoilGrids recommends at most 5 calls/minute."""

    def __init__(self, min_interval: float = 12.0, max_backoff: float = 300.0) -> None:
        self.min_interval = min_interval
        self.max_backoff = max_backoff
        self._lock = threading.Lock()
        self._last_monotonic = 0.0
        self._backoff_until = 0.0
        self._consecutive_failures = 0

    def acquire(self) -> bool:
        now = time.monotonic()
        with self._lock:
            if now < self._backoff_until:
                return False
            if self._last_monotonic and now - self._last_monotonic < self.min_interval:
                return False
            self._last_monotonic = now
            return True

    def note_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._backoff_until = 0.0

    def note_rate_limit(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            delay = min(self.max_backoff, max(self.min_interval, 1.0) * (2**self._consecutive_failures))
            self._backoff_until = time.monotonic() + delay

    def reset(self) -> None:
        with self._lock:
            self._last_monotonic = 0.0
            self._backoff_until = 0.0
            self._consecutive_failures = 0
