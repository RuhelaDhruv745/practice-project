"""Test doubles for the module Protocols (until Members 2 and 3 merge).

These return hand-built contract objects; they encode no real policy. Segments are
supplied explicitly per customer by the test, never computed.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime

from contracts.enums import (
    BlockReason,
    DecisionStatus,
    FindingCode,
    SegmentName,
    Severity,
)
from contracts.interfaces import DraftGenerator, GenerationError, PolicyEngine
from contracts.models import (
    ClassificationResult,
    CustomerProfile,
    DraftContent,
    GeneratedMessage,
    PolicyDecision,
    ReasonCode,
    SegmentAssignment,
    Strategy,
    ValidationFinding,
    ValidationResult,
    VerifiedFacts,
)

FAKE_AS_OF_DATE = date(2026, 1, 15)
FAKE_POLICY_VERSIONS = {"policy": "test", "segments": "test"}


class FakePolicyEngine:
    """Configurable fake ``PolicyEngine``.

    ``segments`` maps customer_id -> primary segment (absent = no segment).
    ``blocked`` maps customer_id -> block reasons for ``decide``.
    ``validation_passes`` controls every ``validate`` result.
    """

    def __init__(
        self,
        segments: Mapping[str, SegmentName] | None = None,
        blocked: Mapping[str, list[BlockReason]] | None = None,
        validation_passes: bool = True,
    ) -> None:
        self.segments = dict(segments or {})
        self.blocked = dict(blocked or {})
        self.validation_passes = validation_passes
        self.calls: list[tuple[str, str]] = []

    def classify(self, profile: CustomerProfile) -> ClassificationResult:
        self.calls.append(("classify", profile.customer_id))
        segment = self.segments.get(profile.customer_id)
        assignments = []
        if segment is not None:
            assignments.append(
                SegmentAssignment(
                    segment=segment,
                    confidence=1.0,
                    reasons=[
                        ReasonCode(
                            code="FAKE_RULE",
                            description="Assigned by the test fake.",
                            evidence={"customer_id": profile.customer_id},
                        )
                    ],
                )
            )
        return ClassificationResult(
            customer_id=profile.customer_id,
            as_of_date=FAKE_AS_OF_DATE,
            segments=assignments,
            primary_segment=segment,
            policy_versions=FAKE_POLICY_VERSIONS,
        )

    def decide(self, profile: CustomerProfile) -> PolicyDecision:
        self.calls.append(("decide", profile.customer_id))
        classification = self.classify(profile)
        reasons = self.blocked.get(profile.customer_id)
        if reasons or classification.primary_segment is None:
            return PolicyDecision(
                customer_id=profile.customer_id,
                status=DecisionStatus.BLOCKED,
                block_reasons=reasons or [BlockReason.NO_ACTIONABLE_SEGMENT],
                classification=classification,
            )
        segment = classification.primary_segment
        strategy = Strategy(
            segment=segment,
            objective="thank",
            tone="warm",
            tone_guidance="Friendly and brief.",
            offer_allowed=False,
        )
        facts = VerifiedFacts(
            customer_id=profile.customer_id,
            first_name=profile.first_name,
            plan=profile.plan,
            segment=segment,
            objective=strategy.objective,
            tone=strategy.tone,
            tone_guidance=strategy.tone_guidance,
        )
        return PolicyDecision(
            customer_id=profile.customer_id,
            status=DecisionStatus.DRAFT_ALLOWED,
            classification=classification,
            strategy=strategy,
            facts=facts,
        )

    def validate(
        self, draft: DraftContent, decision: PolicyDecision
    ) -> ValidationResult:
        self.calls.append(("validate", decision.customer_id))
        if self.validation_passes:
            return ValidationResult(
                passed=True, checks_run=[], validator_version="fake-1"
            )
        return ValidationResult(
            passed=False,
            findings=[
                ValidationFinding(
                    code=FindingCode.BLOCKED_TERM,
                    severity=Severity.BLOCKING,
                    message="Fake blocking finding.",
                )
            ],
            checks_run=[FindingCode.BLOCKED_TERM],
            validator_version="fake-1",
        )


class FakeDraftGenerator:
    """Returns a fixed draft built from the facts' first name and plan only."""

    def __init__(self) -> None:
        self.calls: list[VerifiedFacts] = []

    def generate(self, facts: VerifiedFacts) -> GeneratedMessage:
        self.calls.append(facts)
        return GeneratedMessage(
            message_id=f"MSG-{facts.customer_id}-1",
            customer_id=facts.customer_id,
            draft=DraftContent(
                subject="Thank you for staying with us",
                body=f"Hi {facts.first_name}, thank you for using {facts.plan}.",
            ),
            provider="fake",
            model="fake-model",
            prompt_version="fake-prompt-1",
            generated_at=datetime(2026, 1, 15, 9, 0, tzinfo=UTC),
        )


class FailingDraftGenerator:
    """Always raises ``GenerationError`` (provider failure after retry)."""

    def generate(self, facts: VerifiedFacts) -> GeneratedMessage:
        raise GenerationError("fake provider failure")


class ExplodingPolicyEngine(FakePolicyEngine):
    """Raises an unexpected error, for 500 ``internal_error`` tests."""

    def classify(self, profile: CustomerProfile) -> ClassificationResult:
        raise RuntimeError("Traceback secret-detail person@example.com")


# Static conformance checks: a type checker flags these if a fake drifts.
_policy_engine_check: type[PolicyEngine] = FakePolicyEngine
_generator_check: type[DraftGenerator] = FakeDraftGenerator
_failing_generator_check: type[DraftGenerator] = FailingDraftGenerator
