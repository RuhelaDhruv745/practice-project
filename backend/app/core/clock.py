"""UTC timestamps and opaque IDs for workflow records (not for policy rules).

Policy dates use ``as_of_date`` from the policy YAML; these timestamps only record
when a workflow step happened.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """SQLite drops tzinfo on read; stored values are always UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"
