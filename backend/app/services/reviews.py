"""Review state machine (docs/API_CONTRACTS.md): edit, approve, reject, list.

Approval gating lives here and nowhere else. Approve refuses unless the item is
``pending_review``, its latest validation passed and its decision is
``draft_allowed``; it then re-decides and re-validates immediately before writing the
mock outbox, so stale state can never be delivered.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.core.clock import new_id, utc_now
from backend.app.core.logging import get_logger
from backend.app.middleware.errors import ApiError
from backend.app.repositories import OutboxRepository, ReviewRepository, append_jsonl
from backend.app.services.audit import (
    AuditTrail,
    Details,
    blocking_codes,
    rubric_details,
    validation_details,
)
from backend.app.services.pipeline import load_profile
from contracts.api import ApproveRequest, EditReviewRequest, RejectRequest
from contracts.enums import (
    AuditEventType,
    Channel,
    DecisionStatus,
    MessageStatus,
    ReviewAction,
)
from contracts.interfaces import PolicyEngine
from contracts.models import (
    GeneratedMessage,
    OutboxRecord,
    PolicyDecision,
    Primitive,
    ReviewDecision,
    ReviewItem,
    ValidationResult,
)

_log = get_logger("services.reviews")

DECIDED = frozenset(
    {MessageStatus.APPROVED, MessageStatus.REJECTED, MessageStatus.DELIVERED}
)
# Reviewer edits are attributed to the reviewer, not an LLM provider.
EDIT_PROVIDER = "reviewer"
EDIT_MODEL = "human-edit"
# Used only when the decision carries no offer with its own channel; the mock outbox
# models the email channel of the problem statement.
DEFAULT_CHANNEL = Channel.EMAIL


class ReviewService:
    def __init__(
        self, session: Session, engine: PolicyEngine, outbox_path: Path
    ) -> None:
        self._session = session
        self._engine = engine
        self._outbox_path = outbox_path
        self._reviews = ReviewRepository(session)
        self._audit = AuditTrail(session)

    def list(
        self, status: MessageStatus, limit: int, offset: int
    ) -> tuple[list[ReviewItem], int]:
        return self._reviews.list(status, limit, offset)

    # --- edit ---------------------------------------------------------------

    def edit(self, review_id: str, request: EditReviewRequest) -> ReviewItem:
        item = self._get(review_id)
        if item.status in DECIDED or item.message is None:
            # A policy-blocked item has no message and cannot be edited into one.
            raise ApiError(
                409,
                "review_not_editable",
                "This review item cannot be edited.",
                {"status": item.status.value, "has_message": item.message is not None},
            )
        now = utc_now()
        revision = item.revision + 1
        message = GeneratedMessage(
            message_id=new_id("msg"),
            customer_id=item.customer_id,
            draft=request.draft,
            source="reviewer_edit",
            provider=EDIT_PROVIDER,
            model=EDIT_MODEL,
            prompt_version=item.message.prompt_version,
            generated_at=now,
        )
        validation = self._engine.validate(message.draft, item.decision)
        status = (
            MessageStatus.PENDING_REVIEW if validation.passed else MessageStatus.BLOCKED
        )
        decision = self._reviewer_decision(
            review_id, ReviewAction.EDIT, request.reviewer_id, request.comment, None
        )
        updated = item.model_copy(
            update={
                "status": status,
                "revision": revision,
                "message": message,
                "validation": validation,
                "decisions": [*item.decisions, decision],
                "updated_at": now,
            }
        )
        self._reviews.save(updated)
        versions = item.decision.classification.policy_versions
        self._audit.record(
            AuditEventType.REVIEW_EDITED,
            actor=request.reviewer_id,
            customer_id=item.customer_id,
            review_id=review_id,
            message=message,
            policy_versions=versions,
            details={
                "revision": revision,
                "previous_status": item.status.value,
                "has_comment": bool(request.comment),
            },
        )
        self._audit.record(
            AuditEventType.DRAFT_VALIDATED,
            actor=request.reviewer_id,
            customer_id=item.customer_id,
            review_id=review_id,
            message=message,
            policy_versions=versions,
            details={
                "message_id": message.message_id,
                "revision": revision,
                "status": status.value,
                **validation_details(validation),
            },
        )
        self._session.commit()
        return updated

    # --- approve ------------------------------------------------------------

    def approve(
        self, review_id: str, request: ApproveRequest
    ) -> tuple[ReviewItem, OutboxRecord]:
        item = self._get(review_id)
        if item.status in DECIDED:
            raise self._already_decided(item)

        reasons = self._approval_gate(item)
        if reasons:
            raise self._refuse(item, request.reviewer_id, reasons)
        message = item.message
        assert message is not None  # guaranteed by _approval_gate

        # Re-decide and re-validate immediately before delivery (stale-state defence).
        fresh = self._engine.decide(load_profile(self._session, item.customer_id))
        if fresh.status is not DecisionStatus.DRAFT_ALLOWED:
            raise self._refuse(
                item,
                request.reviewer_id,
                ["decision_blocked"],
                {"block_reasons": [r.value for r in fresh.block_reasons]},
            )
        if fresh.facts != item.decision.facts:
            raise self._refuse(item, request.reviewer_id, ["decision_changed"])
        validation = self._engine.validate(message.draft, fresh)
        self._audit.record(
            AuditEventType.DRAFT_VALIDATED,
            actor=request.reviewer_id,
            customer_id=item.customer_id,
            review_id=review_id,
            message=message,
            policy_versions=fresh.classification.policy_versions,
            details={
                "stage": "pre_delivery",
                "message_id": message.message_id,
                "revision": item.revision,
                **validation_details(validation),
            },
        )
        if not validation.passed:
            item = self._mark_failed(item, validation)
            raise self._refuse(item, request.reviewer_id, ["validation_not_passed"])

        return self._deliver(item, message, request)

    def _approval_gate(self, item: ReviewItem) -> list[str]:
        reasons: list[str] = []
        if item.status is not MessageStatus.PENDING_REVIEW:
            reasons.append("status_not_pending_review")
        if item.validation is None or not item.validation.passed:
            reasons.append("validation_not_passed")
        if item.decision.status is not DecisionStatus.DRAFT_ALLOWED:
            reasons.append("decision_blocked")
        if item.message is None:
            reasons.append("no_message")
        return reasons

    def _mark_failed(
        self, item: ReviewItem, validation: ValidationResult
    ) -> ReviewItem:
        """Record a failed pre-delivery validation as the latest validation."""
        updated = item.model_copy(
            update={
                "status": MessageStatus.BLOCKED,
                "validation": validation,
                "updated_at": utc_now(),
            }
        )
        self._reviews.save(updated)
        return updated

    def _deliver(
        self, item: ReviewItem, message: GeneratedMessage, request: ApproveRequest
    ) -> tuple[ReviewItem, OutboxRecord]:
        now = utc_now()
        decision = self._reviewer_decision(
            item.review_id,
            ReviewAction.APPROVE,
            request.reviewer_id,
            request.comment,
            request,
        )
        updated = item.model_copy(
            update={
                "status": MessageStatus.DELIVERED,
                "decisions": [*item.decisions, decision],
                "updated_at": now,
            }
        )
        record = OutboxRecord(
            message_id=message.message_id,
            review_id=item.review_id,
            customer_id=item.customer_id,
            channel=_channel(item.decision),
            subject=message.draft.subject,
            body=message.draft.body,
            approved_by=request.reviewer_id,
            delivered_at=now,
        )
        versions = item.decision.classification.policy_versions
        self._reviews.save(updated)
        OutboxRepository(self._session).add(record)
        self._audit.record(
            AuditEventType.REVIEW_APPROVED,
            actor=request.reviewer_id,
            customer_id=item.customer_id,
            review_id=item.review_id,
            message=message,
            policy_versions=versions,
            details={
                "revision": item.revision,
                "has_comment": bool(request.comment),
                **rubric_details(request.rubric),
            },
        )
        self._audit.record(
            AuditEventType.MESSAGE_DELIVERED,
            actor=request.reviewer_id,
            customer_id=item.customer_id,
            review_id=item.review_id,
            message=message,
            policy_versions=versions,
            details={"channel": record.channel.value, "delivery": "mock_outbox"},
        )
        self._session.flush()
        # Export before commit: if the export fails the whole delivery rolls back.
        append_jsonl(self._outbox_path, record)
        self._session.commit()
        _log.info("review delivered to mock outbox")
        return updated, record

    # --- reject -------------------------------------------------------------

    def reject(self, review_id: str, request: RejectRequest) -> ReviewItem:
        item = self._get(review_id)
        if item.status in DECIDED:
            raise self._already_decided(item)
        decision = self._reviewer_decision(
            review_id,
            ReviewAction.REJECT,
            request.reviewer_id,
            request.comment,
            request,
        )
        updated = item.model_copy(
            update={
                "status": MessageStatus.REJECTED,
                "decisions": [*item.decisions, decision],
                "updated_at": utc_now(),
            }
        )
        self._reviews.save(updated)
        # The reason itself stays on the review item: free text never enters audit.
        self._audit.record(
            AuditEventType.REVIEW_REJECTED,
            actor=request.reviewer_id,
            customer_id=item.customer_id,
            review_id=review_id,
            message=item.message,
            policy_versions=item.decision.classification.policy_versions,
            details={
                "previous_status": item.status.value,
                "revision": item.revision,
                "reason_recorded": True,
                **rubric_details(request.rubric),
            },
        )
        self._session.commit()
        return updated

    # --- helpers ------------------------------------------------------------

    def _get(self, review_id: str) -> ReviewItem:
        item = self._reviews.get(review_id)
        if item is None:
            raise ApiError(404, "review_not_found", "Review item not found.")
        return item

    @staticmethod
    def _already_decided(item: ReviewItem) -> ApiError:
        return ApiError(
            409,
            "review_already_decided",
            "This review item has already been decided.",
            {"status": item.status.value},
        )

    def _refuse(
        self,
        item: ReviewItem,
        reviewer_id: str,
        reasons: list[str],
        extra: Details | None = None,
    ) -> ApiError:
        """Audit ``delivery_refused`` (committed) and build the 409 error."""
        details: dict[str, Primitive | list[Primitive]] = {
            "status": item.status.value,
            "blocking_findings": blocking_codes(item.validation),
            "reasons": list(reasons),
            **(extra or {}),
        }
        self._audit.record(
            AuditEventType.DELIVERY_REFUSED,
            actor=reviewer_id,
            customer_id=item.customer_id,
            review_id=item.review_id,
            message=item.message,
            policy_versions=item.decision.classification.policy_versions,
            details=details,
        )
        self._session.commit()
        _log.info("delivery refused; reasons=%s", ",".join(reasons))
        return ApiError(
            409,
            "review_not_approvable",
            "This review item cannot be approved.",
            details,
        )

    @staticmethod
    def _reviewer_decision(
        review_id: str,
        action: ReviewAction,
        reviewer_id: str,
        comment: str | None,
        request: ApproveRequest | RejectRequest | None,
    ) -> ReviewDecision:
        return ReviewDecision(
            review_id=review_id,
            action=action,
            reviewer_id=reviewer_id,
            comment=comment,
            rubric=None if request is None else request.rubric,
            decided_at=utc_now(),
        )


def _channel(decision: PolicyDecision) -> Channel:
    facts = decision.facts
    if facts is not None and facts.offer is not None:
        return facts.offer.channel
    return DEFAULT_CHANNEL
