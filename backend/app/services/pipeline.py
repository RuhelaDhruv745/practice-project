"""Pipeline orchestration: profile -> decide -> (generate -> validate) -> review item.

Uses the ``PolicyEngine`` and ``DraftGenerator`` Protocols only. The backend decides
no facts: segment, strategy, offer, reminder stage, amounts and dates all come from
``PolicyEngine.decide``; wording comes from ``DraftGenerator.generate``. A blocked
decision never reaches the generator.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.core.clock import new_id, utc_now
from backend.app.core.logging import get_logger
from backend.app.middleware.errors import ApiError
from backend.app.repositories import CustomerRepository, ReviewRepository
from backend.app.services.audit import AuditTrail, validation_details
from contracts.enums import AuditEventType, DecisionStatus, MessageStatus
from contracts.interfaces import DraftGenerator, GenerationError, PolicyEngine
from contracts.models import (
    CustomerProfile,
    DraftContent,
    GeneratedMessage,
    PolicyDecision,
    ReviewItem,
    ValidationResult,
    VerifiedFacts,
)

_log = get_logger("services.pipeline")


def load_profile(session: Session, customer_id: str) -> CustomerProfile:
    profile = CustomerRepository(session).get_profile(customer_id)
    if profile is None:
        raise ApiError(404, "customer_not_found", "Customer not found.")
    return profile


class PipelineService:
    def __init__(
        self, session: Session, engine: PolicyEngine, generator: DraftGenerator
    ) -> None:
        self._session = session
        self._engine = engine
        self._generator = generator
        self._audit = AuditTrail(session)

    def evaluate(self, customer_id: str) -> PolicyDecision:
        """Decision only: no LLM call, no review item."""
        decision = self._decide(customer_id)
        self._session.commit()
        return decision

    def generate(self, customer_id: str) -> ReviewItem:
        decision = self._decide(customer_id)
        review_id = new_id("rev")
        versions = decision.classification.policy_versions

        if decision.status is DecisionStatus.BLOCKED or decision.facts is None:
            self._audit.record(
                AuditEventType.OUTREACH_BLOCKED,
                customer_id=customer_id,
                review_id=review_id,
                policy_versions=versions,
                details={"block_reasons": [r.value for r in decision.block_reasons]},
            )
            item = self._new_item(review_id, decision, None, None)
        else:
            message = self._generate(decision.facts, versions)
            self._audit.record(
                AuditEventType.DRAFT_GENERATED,
                customer_id=customer_id,
                review_id=review_id,
                message=message,
                policy_versions=versions,
                details={"provider": message.provider, "revision": 1},
            )
            validation = self._engine.validate(message.draft, decision)
            self._audit.record(
                AuditEventType.DRAFT_VALIDATED,
                customer_id=customer_id,
                review_id=review_id,
                message=message,
                policy_versions=versions,
                details={"revision": 1, **validation_details(validation)},
            )
            item = self._new_item(review_id, decision, message, validation)

        ReviewRepository(self._session).add(item)
        self._session.commit()
        _log.info("review item created; status=%s", item.status.value)
        return item

    def validate_draft(self, customer_id: str, draft: DraftContent) -> ValidationResult:
        """Dry run: no audit events, no state change.

        For a blocked decision the policy engine reports the matching
        ``consent_gap`` / ``duplicate_outreach`` finding; the backend adds none.
        """
        profile = load_profile(self._session, customer_id)
        decision = self._engine.decide(profile)
        return self._engine.validate(draft, decision)

    def _decide(self, customer_id: str) -> PolicyDecision:
        # Decision events carry no review_id: when generation fails no item exists.
        profile = load_profile(self._session, customer_id)
        self._audit.profile_assembled(profile)
        decision = self._engine.decide(profile)
        self._audit.decision_events(decision)
        return decision

    def _generate(
        self, facts: VerifiedFacts, versions: dict[str, str]
    ) -> GeneratedMessage:
        try:
            message = self._generator.generate(facts)
            if message.customer_id != facts.customer_id:
                raise GenerationError("draft returned for a different customer")
        except GenerationError as exc:
            # Error type only: provider messages may contain raw model output.
            self._audit.record(
                AuditEventType.GENERATION_FAILED,
                customer_id=facts.customer_id,
                policy_versions=versions,
                details={"error_type": type(exc).__name__},
            )
            self._session.commit()
            _log.warning("draft generation failed; error_type=%s", type(exc).__name__)
            raise ApiError(
                502,
                "generation_failed",
                "The draft could not be generated. No review item was created.",
            ) from None
        return message

    @staticmethod
    def _new_item(
        review_id: str,
        decision: PolicyDecision,
        message: GeneratedMessage | None,
        validation: ValidationResult | None,
    ) -> ReviewItem:
        passed = validation is not None and validation.passed
        now = utc_now()
        return ReviewItem(
            review_id=review_id,
            customer_id=decision.customer_id,
            status=MessageStatus.PENDING_REVIEW if passed else MessageStatus.BLOCKED,
            revision=1,
            decision=decision,
            message=message,
            validation=validation,
            decisions=[],
            created_at=now,
            updated_at=now,
        )
