"""IP-based rate-limiting middleware — sliding window counter.

Tracks per-IP request timestamps inside a sliding 60-second window.
Returns 429 Too Many Requests with a ``Retry-After`` header when the
configured ``rate_limit_rpm`` is exceeded.  Disabled when rpm is 0.

The implementation is in-process (no Redis required) and uses a
``defaultdict[str, deque]`` protected by an ``asyncio.Lock`` so it
stays safe under concurrent requests.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from luna.core.config import APISection

log = logging.getLogger(__name__)

_WINDOW_SECONDS: float = 60.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter keyed on client IP.

    Parameters
    ----------
    app:
        The ASGI application.
    api_config:
        The ``[api]`` section of ``LunaConfig``.
    """

    def __init__(self, app: object, api_config: APISection) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._rpm: int = api_config.rate_limit_rpm
        self._trusted_proxies: frozenset[str] = frozenset(api_config.trusted_proxies)
        self._window: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

        if self._rpm <= 0:
            log.info("API rate limiting disabled (rate_limit_rpm=%d)", self._rpm)
        else:
            log.info("API rate limiting enabled: %d requests/minute", self._rpm)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _client_ip(self, request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For only from trusted proxies.

        Only trusts the ``X-Forwarded-For`` header when the direct connection
        originates from an IP listed in ``trusted_proxies``.  This prevents
        arbitrary clients from spoofing the header to bypass rate limiting.
        """
        direct_ip = request.client.host if request.client else "unknown"

        # Only trust X-Forwarded-For if the direct connection is from a trusted proxy.
        if direct_ip in self._trusted_proxies:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",", 1)[0].strip()

        return direct_ip

    def _purge_expired(self, timestamps: deque[float], now: float) -> None:
        """Remove timestamps older than the sliding window."""
        cutoff = now - _WINDOW_SECONDS
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

    # ------------------------------------------------------------------
    # Middleware dispatch
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Disabled — pass through.
        if self._rpm <= 0:
            return await call_next(request)

        client_ip = self._client_ip(request)
        now = time.monotonic()

        async with self._lock:
            timestamps = self._window[client_ip]
            self._purge_expired(timestamps, now)

            if len(timestamps) >= self._rpm:
                # Compute how long until the oldest entry expires.
                oldest = timestamps[0]
                retry_after = max(1, int(_WINDOW_SECONDS - (now - oldest)) + 1)
                log.warning(
                    "Rate limit exceeded for %s (%d/%d rpm) on %s",
                    client_ip,
                    len(timestamps),
                    self._rpm,
                    request.url.path,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many requests. Please slow down.",
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            timestamps.append(now)

        response = await call_next(request)

        # Attach informational rate-limit headers (non-standard but helpful).
        async with self._lock:
            remaining = max(0, self._rpm - len(self._window[client_ip]))
        response.headers["X-RateLimit-Limit"] = str(self._rpm)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
