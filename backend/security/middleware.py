"""
security/middleware.py
========================
ASGI security middleware and per-IP rate limiter.

Classes
-------
RateLimiter      — sliding-window in-memory rate limiter
SecurityMiddleware — ASGI middleware: rate limiting, injection guard, security headers

Environment variables
---------------------
RATE_LIMIT_PER_MINUTE : requests allowed per IP per 60 s (default 60)
"""
from __future__ import annotations

import logging
import os
import re
import time
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("security.middleware")

RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# Dangerous shell / script patterns (defence-in-depth)
_INJECTION_RE = re.compile(
    r"(\$\{|\$\(|`|<script|javascript:|vbscript:|data:text/html)",
    re.IGNORECASE,
)


class RateLimiter:
    """
    Sliding-window rate limiter (per IP, in-memory).

    Allows up to `limit` requests per 60-second window per IP address.
    Thread-safe enough for a single-process Uvicorn worker.
    """

    def __init__(self, limit: int = RATE_LIMIT_PER_MINUTE) -> None:
        self.limit  = limit
        self.window = 60
        self._buckets: dict[str, deque] = defaultdict(deque)

    def is_allowed(self, ip: str) -> bool:
        now    = time.monotonic()
        bucket = self._buckets[ip]
        cutoff = now - self.window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True


_rate_limiter = RateLimiter()


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Lightweight ASGI middleware that:
      1. Enforces per-IP rate limiting on all routes.
      2. Blocks requests with obviously malicious path/query injections.
      3. Adds security response headers on every response.
    """

    _EXEMPT = {"/", "/docs", "/redoc", "/openapi.json", "/health"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Rate limiting
        if path not in self._EXEMPT:
            client_ip = self._get_ip(request)
            if not _rate_limiter.is_allowed(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down."},
                    headers={"Retry-After": "60"},
                )

        # Path / query injection guard
        if _INJECTION_RE.search(str(request.url)):
            logger.warning("[Security] Suspicious URL blocked: %s", str(request.url)[:200])
            return JSONResponse(
                status_code=400,
                content={"detail": "Request contains forbidden characters."},
            )

        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"]    = "nosniff"
        response.headers["X-Frame-Options"]           = "DENY"
        response.headers["X-XSS-Protection"]          = "1; mode=block"
        response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["Content-Security-Policy"]   = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "frame-ancestors 'none';"
        )
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

    @staticmethod
    def _get_ip(request: Request) -> str:
        """Extract real client IP, respecting CF-Connecting-IP / X-Forwarded-For."""
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip.strip()
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
