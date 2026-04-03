from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if not request.url.path.startswith("/api/v1/research"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - settings.API_RATE_LIMIT_WINDOW_SECONDS
        bucket = self._requests[client]
        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= settings.API_RATE_LIMIT_REQUESTS:
            return JSONResponse(
                status_code=429, content={"detail": "Rate limit exceeded"}
            )

        bucket.append(now)
        return await call_next(request)
