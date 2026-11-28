"""Customer tables per docs/DATABASE_DESIGN.md.

Permitted CustomerProfile fields only: no email, address, age, gender or any other
protected characteristic or proxy. Contradictory billing data (paid with overdue
days) is stored as-is so the policy engine can block it with a reason.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.session import Base


class CustomerRow(Base):
    __tablename__ = "customer"
    __table_args__ = (
        CheckConstraint("months_active >= 0", name="ck_customer_months_active"),
    )

    customer_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(60), nullable=False)
    plan: Mapped[str] = mapped_column(String(40), nullable=False)
    months_active: Mapped[int] = mapped_column(Integer, nullable=False)


class ActivityRow(Base):
    __tablename__ = "activity"
    __table_args__ = (
        CheckConstraint(
            "activity_score_30d >= 0 AND activity_score_30d <= 100",
            name="ck_activity_score_30d",
        ),
        CheckConstraint(
            "activity_score_prev_30d >= 0 AND activity_score_prev_30d <= 100",
            name="ck_activity_score_prev_30d",
        ),
    )

    customer_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("customer.customer_id"), primary_key=True
    )
    # Scores are floats in the contract; asdecimal=False returns float on every DB.
    activity_score_30d: Mapped[float] = mapped_column(
        Numeric(5, 2, asdecimal=False), nullable=False
    )
    activity_score_prev_30d: Mapped[float] = mapped_column(
        Numeric(5, 2, asdecimal=False), nullable=False
    )


class BillingRecordRow(Base):
    __tablename__ = "billing_record"
    __table_args__ = (
        CheckConstraint("days_overdue >= 0", name="ck_billing_days_overdue"),
        CheckConstraint("amount_due >= 0", name="ck_billing_amount_due"),
        CheckConstraint(
            "bill_status IN ('paid', 'due', 'overdue')", name="ck_billing_bill_status"
        ),
        CheckConstraint(
            "on_time_payments_12m >= 0 AND on_time_payments_12m <= 12",
            name="ck_billing_on_time_payments_12m",
        ),
        Index("ix_billing_record_bill_status", "bill_status"),
    )

    customer_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("customer.customer_id"), primary_key=True
    )
    bill_status: Mapped[str] = mapped_column(String(10), nullable=False)
    days_overdue: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_due: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    on_time_payments_12m: Mapped[int] = mapped_column(Integer, nullable=False)


class CommunicationPreferenceRow(Base):
    __tablename__ = "communication_preference"
    __table_args__ = (
        CheckConstraint(
            "last_contacted_days_ago IS NULL OR last_contacted_days_ago >= 0",
            name="ck_comm_last_contacted_days_ago",
        ),
    )

    customer_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("customer.customer_id"), primary_key=True
    )
    consent_marketing: Mapped[bool] = mapped_column(Boolean, nullable=False)
    last_contacted_days_ago: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
