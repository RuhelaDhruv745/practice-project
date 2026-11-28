"""Audit aggregate: append-only. Only ``append`` writes; there is no update/delete."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.app.core.clock import as_utc
from backend.app.models import AuditEventRow
from contracts.enums import AuditEventType
from contracts.models import AuditEvent


def _to_event(row: AuditEventRow) -> AuditEvent:
    return AuditEvent(
        event_id=row.event_id,
        event_type=AuditEventType(row.event_type),
        occurred_at=as_utc(row.occurred_at),
        actor=row.actor,
        customer_id=row.customer_id,
        review_id=row.review_id,
        message_id=row.message_id,
        policy_versions=dict(row.policy_versions),
        prompt_version=row.prompt_version,
        model=row.model,
        details=dict(row.details),
    )


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: AuditEvent) -> None:
        """Insert one event. The ``AuditEvent`` was validated (no emails) on creation."""
        data = event.model_dump(mode="json")
        self._session.add(
            AuditEventRow(
                event_id=event.event_id,
                event_type=event.event_type.value,
                occurred_at=event.occurred_at,
                actor=event.actor,
                customer_id=event.customer_id,
                review_id=event.review_id,
                message_id=event.message_id,
                policy_versions=data["policy_versions"],
                prompt_version=event.prompt_version,
                model=event.model,
                details=data["details"],
            )
        )

    def list(
        self,
        *,
        customer_id: str | None = None,
        review_id: str | None = None,
        event_type: AuditEventType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditEvent], int]:
        """Matching events newest first, and the total match count."""
        query: Select = select(AuditEventRow)
        if customer_id is not None:
            query = query.where(AuditEventRow.customer_id == customer_id)
        if review_id is not None:
            query = query.where(AuditEventRow.review_id == review_id)
        if event_type is not None:
            query = query.where(AuditEventRow.event_type == event_type.value)
        total = self._session.execute(
            select(func.count()).select_from(query.subquery())
        ).scalar_one()
        rows = self._session.scalars(
            query.order_by(AuditEventRow.occurred_at.desc(), AuditEventRow.seq.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_event(r) for r in rows], int(total)
