"""Thread-safe in-memory request rate limiting."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """Fixed-window limiter; process-local by design for the demo deployment."""

    def __init__(self, limit: int = 120, window_s: float = 60.0) -> None:
        if limit < 1 or window_s <= 0:
            raise ValueError("rate limiter limit and window must be positive")
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, *, now: float | None = None) -> bool:
        """Record a hit and return whether it is inside the configured window."""

        current = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            cutoff = current - self.window_s
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(current)
            return True

    def reset(self) -> None:
        """Clear counters, useful for tests and controlled deployments."""

        with self._lock:
            self._hits.clear()
