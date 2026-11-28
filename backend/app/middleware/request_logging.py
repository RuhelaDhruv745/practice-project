"""Access log: method, route template, status and duration only.

The route template (``/api/customers/{customer_id}``) is logged instead of the raw
path so user-supplied path text never reaches the log; bodies are never logged.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from backend.app.core.logging import get_logger

_log = get_logger("access")


def register_request_logging(app: FastAPI) -> None:
    @app.middleware("http")
    async def _log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        template = getattr(route, "path", "<unmatched>")
        _log.info(
            "request method=%s route=%s status=%d duration_ms=%.1f",
            request.method,
            template,
            response.status_code,
            (time.perf_counter() - start) * 1000,
        )
        return response
