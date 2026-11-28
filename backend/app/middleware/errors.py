"""Error handlers: every non-2xx response has the ``ErrorResponse`` shape.

Messages are fixed strings; no stack traces, input values, secrets or raw provider
errors ever reach the client.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.core.logging import get_logger
from contracts.models import ErrorDetail, ErrorResponse, Primitive

_log = get_logger("errors")

_HTTP_CODES = {
    400: ("bad_request", "Bad request."),
    404: ("not_found", "Resource not found."),
    405: ("method_not_allowed", "Method not allowed."),
}


class ApiError(Exception):
    """A documented API error (docs/API_CONTRACTS.md, error table)."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Primitive | list[Primitive]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Primitive | list[Primitive]] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details or {})
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def _field_errors(exc: RequestValidationError) -> list[Primitive]:
    """``location: message`` per error; the offending input value is never echoed."""
    return [
        f"{'.'.join(str(p) for p in err.get('loc', ()))}: {err.get('msg', 'invalid')}"
        for err in exc.errors()
    ]


async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    if any(err.get("type") == "json_invalid" for err in exc.errors()):
        return error_response(400, "bad_request", "Malformed JSON body.")
    return error_response(
        422,
        "validation_error",
        "Request failed schema validation.",
        {"errors": _field_errors(exc)},
    )


async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, message = _HTTP_CODES.get(exc.status_code, ("http_error", "Request failed."))
    return error_response(exc.status_code, code, message)


async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    # Exception type only: messages may contain customer data or provider output.
    _log.error(
        "unhandled error; method=%s error_type=%s",
        request.method,
        type(exc).__name__,
    )
    return error_response(500, "internal_error", "Internal server error.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unhandled)
