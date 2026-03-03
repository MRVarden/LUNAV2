"""Token-based authentication middleware — Bearer scheme.

Reads the expected token from a file on disk (path configured via
APISection.auth_token_file).  Uses hmac.compare_digest for timing-safe
comparison.  Fail-closed: if the token file is absent, ALL requests
(except /health) are rejected with 401.
"""

from __future__ import annotations

import hmac
import logging
from pathlib import Path

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from luna.core.config import APISection

log = logging.getLogger(__name__)

# Paths that are always accessible without authentication.
_PUBLIC_PATHS: frozenset[str] = frozenset({"/health"})


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Verify ``Authorization: Bearer <token>`` on every request.

    Parameters
    ----------
    app:
        The ASGI application.
    api_config:
        The ``[api]`` section of ``LunaConfig``.
    root_dir:
        Project root from which ``auth_token_file`` is resolved.
    """

    def __init__(
        self,
        app: object,
        api_config: APISection,
        root_dir: Path,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._auth_enabled: bool = api_config.auth_enabled
        self._token: str | None = None
        self._token_loaded: bool = False

        if not self._auth_enabled:
            log.info("API authentication disabled by configuration")
            return

        token_path = root_dir / api_config.auth_token_file
        self._load_token(token_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_token(self, path: Path) -> None:
        """Read the token file once at startup."""
        try:
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                log.warning(
                    "Token file %s is empty — all authenticated requests will be refused",
                    path,
                )
                self._token = None
            else:
                self._token = raw
                self._token_loaded = True
                log.info("API token loaded from %s", path)
        except FileNotFoundError:
            log.warning(
                "Token file %s not found — fail-closed: all authenticated "
                "requests will be refused until the file is created and "
                "the application is restarted",
                path,
            )
            self._token = None
        except OSError:
            log.exception(
                "Failed to read token file %s — fail-closed",
                path,
            )
            self._token = None

    @staticmethod
    def _unauthorized(detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": detail},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ------------------------------------------------------------------
    # Middleware dispatch
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Public endpoints bypass auth entirely.
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # If auth is disabled in config, pass through.
        if not self._auth_enabled:
            return await call_next(request)

        # Fail-closed: no valid token on disk.
        if self._token is None:
            log.debug("Rejecting request — no valid token loaded")
            return self._unauthorized(
                "Service authentication is not configured. "
                "Contact the administrator."
            )

        # Extract the Authorization header.
        auth_header = request.headers.get("authorization")
        if not auth_header:
            return self._unauthorized("Missing Authorization header")

        # Must be Bearer scheme.
        parts = auth_header.split(None, 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return self._unauthorized(
                "Invalid Authorization header — expected 'Bearer <token>'"
            )

        provided_token = parts[1]

        # Timing-safe comparison.
        if not hmac.compare_digest(provided_token, self._token):
            log.warning(
                "Invalid API token from %s %s",
                request.client.host if request.client else "unknown",
                request.url.path,
            )
            return self._unauthorized("Invalid or expired token")

        return await call_next(request)
