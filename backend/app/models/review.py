"""Review workflow tables per docs/DATABASE_DESIGN.md: review, generated_message and
outbox_record.

Contract snapshots (``PolicyDecision``, ``ValidationResult``, ``ReviewDecision`` list)
are stored as JSON produced by the contract models, so the repository can rebuild the
exact ``ReviewItem`` the API returned. Status transitions are enforced in the service
layer only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.session import Base


class ReviewRow(Base):
    __tablename__ = "review"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_review_revision"),
        Index("ix_review_status", "status"),
        Index("ix_review_customer_id", "customer_id"),
        Index("ix_review_created_at", "created_at"),
    )

    review_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("customer.customer_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    validation: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # ReviewItem.decisions (reviewer actions), not listed in the ER diagram but part
    # of the ReviewItem contract; stored as a JSON list of ReviewDecision.
    decisions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class GeneratedMessageRow(Base):
    __tablename__ = "generated_message"
    __table_args__ = (
        UniqueConstraint("review_id", "revision", name="uq_message_review_revision"),
        CheckConstraint("source IN ('llm', 'reviewer_edit')", name="ck_message_source"),
        Index("ix_generated_message_review_id", "review_id"),
    )

    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    review_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("review.review_id"), nullable=False
    )
    customer_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("customer.customer_id"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(150), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class OutboxRecordRow(Base):
    __tablename__ = "outbox_record"
    __table_args__ = (Index("ix_outbox_record_customer_id", "customer_id"),)

    message_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("generated_message.message_id"), primary_key=True
    )
    review_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("review.review_id"), nullable=False, unique=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("customer.customer_id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    subject: Mapped[str] = mapped_column(String(150), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(40), nullable=False)
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
