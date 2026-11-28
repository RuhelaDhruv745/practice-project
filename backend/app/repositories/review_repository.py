"""Review aggregate: review row + message revisions <-> ``ReviewItem``.

``ReviewItem.message`` is the latest revision; every revision is kept in
``generated_message`` so edits never overwrite history.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.clock import as_utc
from backend.app.models import GeneratedMessageRow, ReviewRow
from contracts.enums import MessageStatus
from contracts.models import (
    DraftContent,
    GeneratedMessage,
    PolicyDecision,
    ReviewDecision,
    ReviewItem,
    ValidationResult,
)


def _to_message(row: GeneratedMessageRow) -> GeneratedMessage:
    return GeneratedMessage(
        message_id=row.message_id,
        customer_id=row.customer_id,
        draft=DraftContent(subject=row.subject, body=row.body),
        source=row.source,  # type: ignore[arg-type]
        provider=row.provider,
        model=row.model,
        prompt_version=row.prompt_version,
        generated_at=as_utc(row.generated_at),
    )


def _dump_validation(validation: ValidationResult | None) -> dict | None:
    return None if validation is None else validation.model_dump(mode="json")


class ReviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, item: ReviewItem) -> None:
        """Insert a new review item and, if present, its first message revision."""
        self._session.add(
            ReviewRow(
                review_id=item.review_id,
                customer_id=item.customer_id,
                status=item.status.value,
                revision=item.revision,
                decision=item.decision.model_dump(mode="json"),
                validation=_dump_validation(item.validation),
                decisions=[d.model_dump(mode="json") for d in item.decisions],
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )
        self._session.flush()
        if item.message is not None:
            self._add_message(item.review_id, item.revision, item.message)

    def save(self, item: ReviewItem) -> None:
        """Persist an updated item; a new latest message is stored as a new revision.

        The stored ``decision`` snapshot is never changed after creation.
        """
        row = self._session.get(ReviewRow, item.review_id)
        if row is None:
            raise LookupError("review item does not exist")
        row.status = item.status.value
        row.revision = item.revision
        row.validation = _dump_validation(item.validation)
        row.decisions = [d.model_dump(mode="json") for d in item.decisions]
        row.updated_at = item.updated_at
        message = item.message
        if (
            message is not None
            and self._session.get(GeneratedMessageRow, message.message_id) is None
        ):
            self._add_message(item.review_id, item.revision, message)

    def get(self, review_id: str) -> ReviewItem | None:
        row = self._session.get(ReviewRow, review_id)
        return None if row is None else self._to_item(row)

    def list(
        self, status: MessageStatus, limit: int, offset: int
    ) -> tuple[list[ReviewItem], int]:
        """Items with ``status``, newest first, and the total count."""
        query = select(ReviewRow).where(ReviewRow.status == status.value)
        total = self._session.execute(
            select(func.count()).select_from(query.subquery())
        ).scalar_one()
        rows = self._session.scalars(
            query.order_by(ReviewRow.created_at.desc(), ReviewRow.review_id)
            .limit(limit)
            .offset(offset)
        )
        return [self._to_item(r) for r in rows], int(total)

    def _add_message(
        self, review_id: str, revision: int, message: GeneratedMessage
    ) -> None:
        self._session.add(
            GeneratedMessageRow(
                message_id=message.message_id,
                review_id=review_id,
                customer_id=message.customer_id,
                revision=revision,
                subject=message.draft.subject,
                body=message.draft.body,
                provider=message.provider,
                model=message.model,
                prompt_version=message.prompt_version,
                source=message.source,
                generated_at=message.generated_at,
            )
        )

    def _latest_message(self, review_id: str) -> GeneratedMessage | None:
        row = self._session.scalars(
            select(GeneratedMessageRow)
            .where(GeneratedMessageRow.review_id == review_id)
            .order_by(GeneratedMessageRow.revision.desc())
            .limit(1)
        ).one_or_none()
        return None if row is None else _to_message(row)

    def _to_item(self, row: ReviewRow) -> ReviewItem:
        return ReviewItem(
            review_id=row.review_id,
            customer_id=row.customer_id,
            status=MessageStatus(row.status),
            revision=row.revision,
            decision=PolicyDecision.model_validate(row.decision),
            message=self._latest_message(row.review_id),
            validation=(
                None
                if row.validation is None
                else ValidationResult.model_validate(row.validation)
            ),
            decisions=[ReviewDecision.model_validate(d) for d in row.decisions],
            created_at=as_utc(row.created_at),
            updated_at=as_utc(row.updated_at),
        )
