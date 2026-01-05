import time
import random


class SimpleRateLimiter:
    def __init__(self, requests_per_sec: float) -> None:
        if requests_per_sec <= 0:
            raise ValueError("requests_per_sec must be > 0")
        self._min_interval = 1.0 / requests_per_sec
        self._last_ts = 0.0

    def wait(self) -> None:
        now = time.time()
        elapsed = now - self._last_ts
        sleep_for = self._min_interval - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)
        self._last_ts = time.time()


def backoff_sleep(attempt: int, base: float = 0.5, cap: float = 8.0) -> None:
    t = min(cap, base * (2 ** attempt))
    t *= 0.7 + random.random() * 0.6
    time.sleep(t)
