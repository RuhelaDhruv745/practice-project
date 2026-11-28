"""The fakes honour the contracts, so backend tests exercise real model rules."""

from __future__ import annotations

import pytest

from backend.app.services.unwired import (
    NotWiredError,
    UnwiredDraftGenerator,
    UnwiredPolicyEngine,
)
from backend.tests.fakes import (
    FailingDraftGenerator,
    FakeDraftGenerator,
    FakePolicyEngine,
)
from contracts.enums import BlockReason, DecisionStatus, SegmentName
from contracts.interfaces import GenerationError
from contracts.models import CustomerProfile, DraftContent

PROFILE = CustomerProfile(
    customer_id="CUST-010",
    first_name="Asha",
    consent_marketing=True,
    plan="Value 299",
    months_active=20,
    activity_score_30d=70,
    activity_score_prev_30d=72,
    on_time_payments_12m=12,
    bill_status="paid",
    days_overdue=0,
    amount_due="0.00",
    due_date=None,
)


def test_fake_policy_engine_allowed_path() -> None:
    engine = FakePolicyEngine(segments={"CUST-010": SegmentName.CONSISTENT})

    decision = engine.decide(PROFILE)
    message = FakeDraftGenerator().generate(decision.facts)
    validation = engine.validate(message.draft, decision)

    assert decision.status is DecisionStatus.DRAFT_ALLOWED
    assert message.customer_id == "CUST-010"
    assert validation.passed


def test_fake_policy_engine_blocked_and_failing_validation() -> None:
    engine = FakePolicyEngine(
        segments={"CUST-010": SegmentName.CONSISTENT},
        blocked={"CUST-010": [BlockReason.NO_MARKETING_CONSENT]},
        validation_passes=False,
    )

    decision = engine.decide(PROFILE)
    validation = engine.validate(DraftContent(subject="s", body="b"), decision)

    assert decision.status is DecisionStatus.BLOCKED
    assert decision.facts is None
    assert not validation.passed


def test_fake_without_segment_blocks_with_no_actionable_segment() -> None:
    decision = FakePolicyEngine().decide(PROFILE)

    assert decision.block_reasons == [BlockReason.NO_ACTIONABLE_SEGMENT]


def test_failing_generator_raises_generation_error() -> None:
    facts = FakePolicyEngine(segments={"CUST-010": SegmentName.CONSISTENT}).decide(
        PROFILE
    )
    with pytest.raises(GenerationError):
        FailingDraftGenerator().generate(facts.facts)


def test_unwired_stand_ins_refuse_every_call() -> None:
    with pytest.raises(NotWiredError):
        UnwiredPolicyEngine().classify(PROFILE)
    with pytest.raises(NotWiredError):
        UnwiredDraftGenerator().generate(None)  # type: ignore[arg-type]
