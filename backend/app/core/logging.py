"""Logging setup that redacts email addresses and API-key-like tokens.

Code must not log emails, keys or message bodies in the first place; the redaction
filter is a second line of defence for anything that slips through (for example a
user-supplied value echoed in a third-party log line).
"""

from __future__ import annotations

import logging
import re

LOGGER_NAME = "backend"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_KEY_RE = re.compile(r"\b(?:sk-ant-|sk-|gsk_)[A-Za-z0-9_-]{8,}")
_AT_RE = re.compile(r"@")

_HANDLER_NAME = "backend-redacting-handler"
# uvicorn logs raw request paths (which may hold user text) directly to these
# loggers, so a logger-level filter redacts them before any handler sees them.
_SERVER_LOGGERS = ("uvicorn.access", "uvicorn.error")


def redact(text: str) -> str:
    """Mask emails, key-like tokens and any remaining ``@`` in a log line."""
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _KEY_RE.sub("[redacted-key]", text)
    return _AT_RE.sub("[at]", text)


def _redact_arg(value: object) -> object:
    """Numbers and booleans pass through unchanged so ``%d`` formatting still works.
    Every other value is redacted as text."""
    if value is None or isinstance(value, int | float):
        return value
    return redact(str(value))


class RedactingFilter(logging.Filter):
    """Redacts the message template and each argument in place.

    ``record.args`` keeps its shape (tuple or mapping) because some formatters
    unpack it. For example, uvicorn's ``AccessFormatter`` unpacks
    ``(client_addr, method, full_path, http_version, status_code)``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not isinstance(record.msg, str):
            # Non-string message objects are rendered once, then redacted.
            record.msg = redact(record.getMessage())
            record.args = ()
            return True
        record.msg = redact(record.msg)
        args = record.args
        if isinstance(args, tuple):
            record.args = tuple(_redact_arg(a) for a in args)
        elif isinstance(args, dict):
            record.args = {k: _redact_arg(v) for k, v in args.items()}
        return True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def configure_logging(level: str = "INFO") -> None:
    """Attach one redacting stream handler to the ``backend`` logger and a redacting
    filter to the uvicorn loggers (idempotent)."""
    for name in _SERVER_LOGGERS:
        server_logger = logging.getLogger(name)
        if not any(isinstance(f, RedactingFilter) for f in server_logger.filters):
            server_logger.addFilter(RedactingFilter())
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    if any(h.get_name() == _HANDLER_NAME for h in logger.handlers):
        return
    handler = logging.StreamHandler()
    handler.set_name(_HANDLER_NAME)
    handler.addFilter(RedactingFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(handler)
