"""Contract invariants that every module relies on."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from contracts.enums import (
    AuditEventType,
    BillStatus,
    BlockReason,
    DecisionStatus,
    FindingCode,
    SegmentName,
    Severity,
)
from contracts.models import (
    AuditEvent,
    ClassificationResult,
    CustomerProfile,
    DraftContent,
    PolicyDecision,
    ReasonCode,
    SegmentAssignment,
    Strategy,
    ValidationFinding,
    ValidationResult,
    VerifiedFacts,
)

NOW = datetime(2026, 11, 28, 12, 0, tzinfo=UTC)


def _profile(**overrides) -> dict:
    base = {
        "customer_id": "CUST-001",
        "first_name": "Asha",
        "consent_marketing": True,
        "plan": "Postpaid 599",
        "months_active": 30,
        "activity_score_30d": 72,
        "activity_score_prev_30d": 70,
        "on_time_payments_12m": 12,
        "bill_status": "paid",
        "days_overdue": 0,
        "amount_due": "0.00",
        "due_date": None,
        "last_contacted_days_ago": 40,
    }
    return base | overrides


def _classification(segment: SegmentName | None = SegmentName.CONSISTENT):
    segments = []
    if segment is not None:
        reason = ReasonCode(
            code="ON_TIME_PAYMENTS", description="12 of 12", evidence={}
        )
        segments = [
            SegmentAssignment(segment=segment, confidence=0.9, reasons=[reason])
        ]
    return ClassificationResult(
        customer_id="CUST-001",
        as_of_date=date(2026, 11, 28),
        segments=segments,
        primary_segment=segment,
        policy_versions={"segments": "1.0"},
    )


def _strategy() -> Strategy:
    return Strategy(
        segment=SegmentName.CONSISTENT,
        objective="thank",
        tone="warm_appreciative",
        tone_guidance="Warm.",
        offer_allowed=False,
    )


def _facts() -> VerifiedFacts:
    return VerifiedFacts(
        customer_id="CUST-001",
        first_name="Asha",
        plan="Postpaid 599",
        segment=SegmentName.CONSISTENT,
        objective="thank",
        tone="warm_appreciative",
        tone_guidance="Warm.",
    )


def test_profile_accepts_permitted_fields() -> None:
    profile = CustomerProfile(**_profile())
    assert profile.bill_status is BillStatus.PAID
    assert profile.amount_due == Decimal("0.00")


@pytest.mark.parametrize("field", ["email", "age", "gender", "religion", "postcode"])
def test_profile_rejects_unpermitted_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        CustomerProfile(**_profile(**{field: "x"}))


def test_profile_allows_contradictory_billing_so_policy_can_block_it() -> None:
    profile = CustomerProfile(**_profile(bill_status="paid", days_overdue=12))
    assert profile.days_overdue == 12


def test_profile_rejects_bad_customer_id() -> None:
    with pytest.raises(ValidationError):
        CustomerProfile(**_profile(customer_id="42"))


def test_primary_segment_must_be_assigned() -> None:
    with pytest.raises(ValidationError):
        ClassificationResult(
            customer_id="CUST-001",
            as_of_date=date(2026, 11, 28),
            segments=[],
            primary_segment=SegmentName.DORMANT,
            policy_versions={},
        )


def test_blocked_decision_needs_reason_and_no_facts() -> None:
    with pytest.raises(ValidationError):
        PolicyDecision(
            customer_id="CUST-001",
            status=DecisionStatus.BLOCKED,
            classification=_classification(),
        )
    with pytest.raises(ValidationError):
        PolicyDecision(
            customer_id="CUST-001",
            status=DecisionStatus.BLOCKED,
            block_reasons=[BlockReason.NO_MARKETING_CONSENT],
            classification=_classification(),
            facts=_facts(),
        )


def test_allowed_decision_needs_facts_and_strategy() -> None:
    with pytest.raises(ValidationError):
        PolicyDecision(
            customer_id="CUST-001",
            status=DecisionStatus.DRAFT_ALLOWED,
            classification=_classification(),
        )
    decision = PolicyDecision(
        customer_id="CUST-001",
        status=DecisionStatus.DRAFT_ALLOWED,
        classification=_classification(),
        strategy=_strategy(),
        facts=_facts(),
    )
    assert decision.facts is not None


def test_draft_content_is_subject_and_body_only() -> None:
    with pytest.raises(ValidationError):
        DraftContent(subject="Hi", body="Thanks", offer_id="FREE-100")


def test_validation_passed_flag_matches_blocking_findings() -> None:
    finding = ValidationFinding(
        code=FindingCode.BLOCKED_TERM, severity=Severity.BLOCKING, message="x"
    )
    with pytest.raises(ValidationError):
        ValidationResult(
            passed=True,
            findings=[finding],
            checks_run=[FindingCode.BLOCKED_TERM],
            validator_version="1",
        )
    result = ValidationResult(
        passed=False,
        findings=[finding],
        checks_run=[FindingCode.BLOCKED_TERM],
        validator_version="1",
    )
    assert not result.passed


def test_audit_event_rejects_email_addresses() -> None:
    with pytest.raises(ValidationError, match="email"):
        AuditEvent(
            event_id="e1",
            event_type=AuditEventType.MESSAGE_DELIVERED,
            occurred_at=NOW,
            actor="system",
            details={"recipient": "someone@example.com"},
        )


def test_models_are_immutable() -> None:
    profile = CustomerProfile(**_profile())
    with pytest.raises(ValidationError):
        profile.amount_due = Decimal("999")


def test_reject_decision_needs_reason() -> None:
    from contracts.enums import ReviewAction
    from contracts.models import ReviewDecision

    with pytest.raises(ValidationError):
        ReviewDecision(
            review_id="r1",
            action=ReviewAction.REJECT,
            reviewer_id="reviewer-1",
            decided_at=NOW,
        )


def test_audit_actor_cannot_be_email() -> None:
    with pytest.raises(ValidationError):
        AuditEvent(
            event_id="e1",
            event_type=AuditEventType.REVIEW_APPROVED,
            occurred_at=NOW,
            actor="reviewer@example.com",
        )


def test_api_bodies() -> None:
    from contracts.api import CustomerSummary, Page, RejectRequest

    with pytest.raises(ValidationError):
        RejectRequest(reviewer_id="reviewer-1", comment="   ")
    with pytest.raises(ValidationError):
        RejectRequest(reviewer_id="Reviewer One", comment="wrong tone")
    page = Page[CustomerSummary](items=[], total=0)
    assert page.total == 0
