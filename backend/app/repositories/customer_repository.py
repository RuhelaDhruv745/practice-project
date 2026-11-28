"""Customer aggregate: the only place customer rows become a ``CustomerProfile``.

Selects the permitted profile columns only (FR-01); nothing else leaves this module.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models import (
    ActivityRow,
    BillingRecordRow,
    CommunicationPreferenceRow,
    CustomerRow,
)
from contracts.models import CustomerProfile

_log = get_logger("repositories.customer")

# Column for every CustomerProfile field, labelled with the field name.
_PROFILE_COLUMNS = {
    "customer_id": CustomerRow.customer_id,
    "first_name": CustomerRow.first_name,
    "consent_marketing": CommunicationPreferenceRow.consent_marketing,
    "plan": CustomerRow.plan,
    "months_active": CustomerRow.months_active,
    "activity_score_30d": ActivityRow.activity_score_30d,
    "activity_score_prev_30d": ActivityRow.activity_score_prev_30d,
    "on_time_payments_12m": BillingRecordRow.on_time_payments_12m,
    "bill_status": BillingRecordRow.bill_status,
    "days_overdue": BillingRecordRow.days_overdue,
    "amount_due": BillingRecordRow.amount_due,
    "due_date": BillingRecordRow.due_date,
    "last_contacted_days_ago": CommunicationPreferenceRow.last_contacted_days_ago,
}

if set(_PROFILE_COLUMNS) != set(CustomerProfile.model_fields):  # pragma: no cover
    raise RuntimeError("customer column map is out of sync with CustomerProfile")


class CorruptCustomerRecordError(RuntimeError):
    """A stored customer row does not form a valid CustomerProfile (bad seed data)."""


def _profile_query() -> Select:
    return (
        select(*(col.label(name) for name, col in _PROFILE_COLUMNS.items()))
        .select_from(CustomerRow)
        .join(ActivityRow, ActivityRow.customer_id == CustomerRow.customer_id)
        .join(BillingRecordRow, BillingRecordRow.customer_id == CustomerRow.customer_id)
        .join(
            CommunicationPreferenceRow,
            CommunicationPreferenceRow.customer_id == CustomerRow.customer_id,
        )
    )


def _to_profile(mapping: dict) -> CustomerProfile:
    try:
        return CustomerProfile.model_validate(dict(mapping))
    except ValidationError as exc:
        # Field names only: values may be customer text.
        fields = sorted({str(err["loc"][0]) for err in exc.errors() if err["loc"]})
        _log.error("stored customer record is invalid; fields=%s", fields)
        raise CorruptCustomerRecordError("stored customer record is invalid") from None


class CustomerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_profile(self, customer_id: str) -> CustomerProfile | None:
        query = _profile_query().where(CustomerRow.customer_id == customer_id)
        row = self._session.execute(query).mappings().one_or_none()
        return None if row is None else _to_profile(row)

    def list_profiles(
        self, limit: int | None = None, offset: int = 0
    ) -> list[CustomerProfile]:
        query = _profile_query().order_by(CustomerRow.customer_id).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return [_to_profile(r) for r in self._session.execute(query).mappings()]

    def count(self) -> int:
        query = select(func.count()).select_from(_profile_query().subquery())
        return int(self._session.execute(query).scalar_one())

    def upsert(self, profile: CustomerProfile, now: datetime | None = None) -> bool:
        """Insert or update one customer across its four tables.

        Returns True when anything changed, so re-seeding identical data is a no-op
        (``updated_at`` is only touched when contact preferences change).
        """
        now = now or datetime.now(UTC)
        changed = False
        rows = (
            CustomerRow(
                customer_id=profile.customer_id,
                first_name=profile.first_name,
                plan=profile.plan,
                months_active=profile.months_active,
            ),
            ActivityRow(
                customer_id=profile.customer_id,
                activity_score_30d=profile.activity_score_30d,
                activity_score_prev_30d=profile.activity_score_prev_30d,
            ),
            BillingRecordRow(
                customer_id=profile.customer_id,
                bill_status=profile.bill_status.value,
                days_overdue=profile.days_overdue,
                amount_due=profile.amount_due,
                due_date=profile.due_date,
                on_time_payments_12m=profile.on_time_payments_12m,
            ),
        )
        for new in rows:
            changed |= self._merge(new)

        pref = self._session.get(CommunicationPreferenceRow, profile.customer_id)
        if pref is None:
            self._session.add(
                CommunicationPreferenceRow(
                    customer_id=profile.customer_id,
                    consent_marketing=profile.consent_marketing,
                    last_contacted_days_ago=profile.last_contacted_days_ago,
                    updated_at=now,
                )
            )
            changed = True
        elif (pref.consent_marketing, pref.last_contacted_days_ago) != (
            profile.consent_marketing,
            profile.last_contacted_days_ago,
        ):
            pref.consent_marketing = profile.consent_marketing
            pref.last_contacted_days_ago = profile.last_contacted_days_ago
            pref.updated_at = now
            changed = True
        return changed

    def _merge(self, new: CustomerRow | ActivityRow | BillingRecordRow) -> bool:
        existing = self._session.get(type(new), new.customer_id)
        if existing is None:
            self._session.add(new)
            return True
        changed = False
        for column in type(new).__table__.columns.keys():
            value = getattr(new, column)
            if getattr(existing, column) != value:
                setattr(existing, column, value)
                changed = True
        return changed
