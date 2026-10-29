import math
import threading
from collections.abc import Hashable
from datetime import datetime


class AttemptLimiter:
    """Remembers recent failures per key and says how long a blocked key must wait.

    Kept in the memory of the process: enough for one server, and it needs no extra service.
    Times come from the caller (the Clock), so tests control them.
    """

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failures: dict[Hashable, list[datetime]] = {}
        self._lock = threading.Lock()

    def check(self, key: Hashable, now: datetime) -> int | None:
        """Seconds to wait when the key is blocked, otherwise None."""
        with self._lock:
            recent = self._recent(key, now)
            if len(recent) < self.max_attempts:
                return None
            # The key is free again when enough old failures have left the window.
            leaves_at = recent[len(recent) - self.max_attempts]
            wait = self.window_seconds - (now - leaves_at).total_seconds()
            return max(1, math.ceil(wait))

    def record_failure(self, key: Hashable, now: datetime) -> None:
        with self._lock:
            self._failures.setdefault(key, self._recent(key, now)).append(now)

    def clear(self, key: Hashable) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def _recent(self, key: Hashable, now: datetime) -> list[datetime]:
        recent = [
            moment
            for moment in self._failures.get(key, [])
            if (now - moment).total_seconds() < self.window_seconds
        ]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent
