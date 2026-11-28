"""Mock outbox: an ``outbox_record`` row plus one JSON line in ``outputs/outbox.jsonl``.

Nothing here (or anywhere in the backend) sends email or opens a network connection.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.clock import as_utc
from backend.app.models import OutboxRecordRow
from contracts.enums import Channel
from contracts.models import OutboxRecord


class OutboxRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: OutboxRecord) -> None:
        self._session.add(
            OutboxRecordRow(
                message_id=record.message_id,
                review_id=record.review_id,
                customer_id=record.customer_id,
                channel=record.channel.value,
                subject=record.subject,
                body=record.body,
                approved_by=record.approved_by,
                delivered_at=record.delivered_at,
            )
        )

    def list_all(self) -> list[OutboxRecord]:
        rows = self._session.scalars(
            select(OutboxRecordRow).order_by(OutboxRecordRow.delivered_at)
        )
        return [
            OutboxRecord(
                message_id=r.message_id,
                review_id=r.review_id,
                customer_id=r.customer_id,
                channel=Channel(r.channel),
                subject=r.subject,
                body=r.body,
                approved_by=r.approved_by,
                delivered_at=as_utc(r.delivered_at),
            )
            for r in rows
        ]


def append_jsonl(path: Path, record: OutboxRecord) -> None:
    """Append one record as a JSON line (the mock delivery export)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")
