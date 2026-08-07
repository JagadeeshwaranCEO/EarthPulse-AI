"""Request throttling + optional API-key guard for mutating endpoints.

Dev posture: rate limiting is ON (cheap in-memory sliding window — no Redis
dependency), the API key is OFF by default so the keyless copilot keeps working.
Set `EARTHPULSE_API_KEY` to enforce the key in CI/prod. `GET` routes are never
gated — only the POST routes that mutate state.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import deque
from typing import Callable

from fastapi import Depends, HTTPException, Request

from app.config import get_settings


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class SlidingWindowRateLimiter:
    """Per-client sliding-window limiter; old hits are pruned on access."""

    def __init__(self, limit: float, window_s: float):
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        """Record a hit; returns True if the request is allowed."""
        now = time.monotonic()
        with self._lock:
            queue = self._hits.get(key)
            if queue is None:
                self._hits[key] = deque([now])
                return True
            while queue and now - queue[0] > self.window_s:
                queue.popleft()
            if len(queue) >= self.limit:
                return False
            queue.append(now)
            return True

    def reset(self) -> None:
        """Test hook — clear all buckets."""
        with self._lock:
            self._hits.clear()


# Shared buckets: every mutating endpoint funnels through these two instances,
# so tests can flush them between suites.
_MUTATION_LIMITER = SlidingWindowRateLimiter(
    limit=float(get_settings().mutation_rate_per_minute), window_s=60.0
)
_CHAT_LIMITER = SlidingWindowRateLimiter(
    limit=float(get_settings().mutation_rate_per_minute), window_s=60.0
)


def mutation_guard(*, require_api_key: bool = True) -> Callable[[Request], None]:
    """Dependency factory: throttles the client and (optionally) checks the key.

    Chat is user-facing conversational input — use `require_api_key=False` so the
    keyless copilot UX stays intact, but it still gets throttled.
    """
    limiter = _CHAT_LIMITER if not require_api_key else _MUTATION_LIMITER

    def dependency(request: Request) -> None:
        settings = get_settings()
        client = _client_ip(request)

        if require_api_key and settings.api_key:
            provided = request.headers.get("x-api-key", "")
            if not provided or not secrets.compare_digest(provided, settings.api_key):
                raise HTTPException(401, "missing or invalid X-API-Key header")

        if not limiter.hit(client):
            raise HTTPException(429, "rate limit exceeded — retry in a minute")

    return dependency


def rate_limited() -> Callable[[Request], None]:
    """Throttle-only guard (used by chat: no key requirement, still throttled)."""
    return mutation_guard(require_api_key=False)


# Pre-built dependencies for the mutating endpoints.
require_api_key = Depends(mutation_guard(require_api_key=True))
chat_throttle = Depends(mutation_guard(require_api_key=False))


def reset_mutation_limiters() -> None:
    """Test hook — flush the shared rate-limit buckets (mirrors ticker.reset())."""
    _MUTATION_LIMITER.reset()
    _CHAT_LIMITER.reset()
