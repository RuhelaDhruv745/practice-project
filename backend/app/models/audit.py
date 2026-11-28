"""Append-only audit table per docs/DATABASE_DESIGN.md.

Rows are only ever inserted from a validated ``AuditEvent`` (which rejects email
addresses); the repository exposes no update or delete. ``seq`` is a surrogate
autoincrement key so "newest first" is stable even when two events share a timestamp;
``event_id`` stays unique.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.session import Base


class AuditEventRow(Base):
    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_occurred_at", "occurred_at"),
        Index("ix_audit_event_customer_id", "customer_id"),
        Index("ix_audit_event_review_id", "review_id"),
        Index("ix_audit_event_event_type", "event_type"),
    )

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actor: Mapped[str] = mapped_column(String(60), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    review_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_versions: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
