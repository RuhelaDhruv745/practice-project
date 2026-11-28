"""Builds and appends ``AuditEvent`` records.

Every event goes through the ``AuditEvent`` contract, which rejects email addresses
in ``actor`` and ``details``. Details hold IDs, codes, counts and flags only: never
message bodies, reviewer comments or customer text.
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.orm import Session

from backend.app.core.clock import new_id, utc_now
from backend.app.repositories import AuditRepository
from contracts.enums import AuditEventType, Severity
from contracts.models import (
    AuditEvent,
    CustomerProfile,
    GeneratedMessage,
    PolicyDecision,
    Primitive,
    ReviewRubric,
    ValidationResult,
)

SYSTEM_ACTOR = "system"

Details = dict[str, Primitive | list[Primitive]]


def validation_details(validation: ValidationResult) -> Details:
    return {
        "passed": validation.passed,
        "finding_codes": [f.code.value for f in validation.findings],
        "blocking_findings": blocking_codes(validation),
        "validator_version": validation.validator_version,
    }


def blocking_codes(validation: ValidationResult | None) -> list[Primitive]:
    if validation is None:
        return []
    return [
        f.code.value for f in validation.findings if f.severity is Severity.BLOCKING
    ]


def rubric_details(rubric: ReviewRubric | None) -> Details:
    if rubric is None:
        return {"rubric_provided": False}
    scores: Details = {f"rubric_{k}": v for k, v in rubric.model_dump().items()}
    return {"rubric_provided": True, **scores}


class AuditTrail:
    """Appends audit events in the caller's transaction (the caller commits)."""

    def __init__(self, session: Session) -> None:
        self._repo = AuditRepository(session)

    def record(
        self,
        event_type: AuditEventType,
        *,
        actor: str = SYSTEM_ACTOR,
        customer_id: str | None = None,
        review_id: str | None = None,
        message: GeneratedMessage | None = None,
        message_id: str | None = None,
        policy_versions: Mapping[str, str] | None = None,
        details: Details | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=new_id("evt"),
            event_type=event_type,
            occurred_at=utc_now(),
            actor=actor,
            customer_id=customer_id,
            review_id=review_id,
            message_id=message.message_id if message is not None else message_id,
            policy_versions=dict(policy_versions or {}),
            prompt_version=message.prompt_version if message is not None else None,
            model=message.model if message is not None else None,
            details=details or {},
        )
        self._repo.append(event)
        return event

    def profile_assembled(self, profile: CustomerProfile) -> None:
        self.record(
            AuditEventType.PROFILE_ASSEMBLED,
            customer_id=profile.customer_id,
            details={"fields": sorted(CustomerProfile.model_fields)},
        )

    def decision_events(self, decision: PolicyDecision) -> None:
        """``classified`` then ``policy_decided`` for one ``PolicyDecision``."""
        classification = decision.classification
        versions = classification.policy_versions
        self.record(
            AuditEventType.CLASSIFIED,
            customer_id=decision.customer_id,
            policy_versions=versions,
            details={
                "as_of_date": classification.as_of_date.isoformat(),
                "primary_segment": (
                    None
                    if classification.primary_segment is None
                    else classification.primary_segment.value
                ),
                "segments": [s.segment.value for s in classification.segments],
                "reason_codes": [
                    r.code for s in classification.segments for r in s.reasons
                ],
            },
        )
        facts = decision.facts
        self.record(
            AuditEventType.POLICY_DECIDED,
            customer_id=decision.customer_id,
            policy_versions=versions,
            details={
                "status": decision.status.value,
                "block_reasons": [r.value for r in decision.block_reasons],
                "objective": (
                    None if decision.strategy is None else decision.strategy.objective
                ),
                "offer_id": (
                    None
                    if facts is None or facts.offer is None
                    else facts.offer.offer_id
                ),
                "reminder_stage": (
                    None
                    if facts is None or facts.reminder is None
                    else facts.reminder.stage
                ),
                "eligible_offers": [
                    c.offer_id for c in decision.offer_checks if c.eligible
                ],
            },
        )
