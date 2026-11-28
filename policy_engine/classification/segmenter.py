"""Deterministic segment rules, reason codes and confidence.

Rules (thresholds come only from ``data/policies/segments.yaml``):

- ``payment_reminder``: ``bill_status == overdue``. Whether the billing record is
  consistent enough to act on is a separate gate in ``decide``.
- ``dormant``: ``activity_score_30d < dormant_max_activity`` (strict).
- ``declining``: ``activity_score_prev_30d > 0`` and the drop from the previous to the
  current 30 days is at least ``declining_min_drop_pct`` percent (exactly the
  threshold counts). Computed in ``Decimal`` so 30% is exactly 30%.
- ``loyalty_candidate``: ``months_active >= loyalty_min_months_active``,
  ``on_time_payments_12m >= loyalty_min_on_time_payments``,
  ``activity_score_30d >= loyalty_min_activity`` and the bill is not overdue.
- ``consistent``: ``on_time_payments_12m >= consistent_min_on_time_payments``,
  ``activity_score_30d >= consistent_min_activity`` and the bill is not overdue.

A customer may match several segments; the primary one is the first matching entry
of ``priority`` in ``segments.yaml``. Only behavioural and billing fields are used;
``first_name`` and ``plan`` are never read by any rule.

Confidence (deterministic, in [0.5, 1.0]):

    For each numeric condition of a segment:
        distance = how far the value is past the threshold, on the passing side (>= 0)
        span     = distance from the threshold to the field's natural bound on that
                   side (Score: 0..100, on-time payments: 0..12, drop %: up to 100);
                   for unbounded fields (months_active) span = the threshold itself
        condition_confidence = 0.5 + 0.5 * min(1, distance / span)   (1.0 if span <= 0)
    segment confidence = min over its numeric conditions, rounded to 4 decimals;
    a segment decided only by a categorical field (bill_status) has confidence 1.0.

So a value exactly on its threshold gives 0.5 and a value at the far end of its range
gives 1.0. The bounds are the contract ranges of ``CustomerProfile`` fields, not policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from contracts.enums import BillStatus, SegmentName
from contracts.models import (
    ClassificationResult,
    CustomerProfile,
    ReasonCode,
    SegmentAssignment,
)
from policy_engine.config_loader import Policy

# Natural ranges of CustomerProfile fields (contracts.models), used only for confidence.
SCORE_MIN = Decimal(0)
SCORE_MAX = Decimal(100)
ON_TIME_MAX = Decimal(12)
DROP_PCT_MAX = Decimal(100)

_FLOOR = Decimal("0.5")
_HUNDRED = Decimal(100)


def _dec(value: float | int) -> Decimal:
    """Exact decimal of the value as written (avoids binary float artefacts)."""
    return Decimal(str(value))


def condition_confidence(distance: Decimal, span: Decimal) -> float:
    """0.5 at the threshold, rising linearly to 1.0 at the end of the span."""
    if span <= 0:
        return 1.0
    ratio = min(Decimal(1), max(Decimal(0), distance / span))
    return float(round(_FLOOR + _FLOOR * ratio, 4))


def _at_least(value: Decimal, threshold: Decimal, upper: Decimal | None) -> float:
    span = (upper - threshold) if upper is not None else threshold
    return condition_confidence(value - threshold, span)


def _below(value: Decimal, threshold: Decimal, lower: Decimal) -> float:
    return condition_confidence(threshold - value, threshold - lower)


@dataclass(frozen=True)
class _Match:
    segment: SegmentName
    confidence: float
    reasons: tuple[ReasonCode, ...]

    def assignment(self) -> SegmentAssignment:
        return SegmentAssignment(
            segment=self.segment,
            confidence=self.confidence,
            reasons=list(self.reasons),
        )


def drop_pct(profile: CustomerProfile) -> Decimal | None:
    """Percentage drop from previous to current 30-day activity; None if prev is 0."""
    prev = _dec(profile.activity_score_prev_30d)
    if prev <= 0:
        return None
    return (prev - _dec(profile.activity_score_30d)) / prev * _HUNDRED


def _not_overdue_reason(profile: CustomerProfile) -> ReasonCode:
    return ReasonCode(
        code="NO_OVERDUE_BILL",
        description="The current bill is not overdue.",
        evidence={"bill_status": profile.bill_status.value},
    )


def _on_time_reason(profile: CustomerProfile, minimum: int) -> ReasonCode:
    return ReasonCode(
        code="ON_TIME_PAYMENTS",
        description=f"At least {minimum} of the last 12 payments were on time.",
        evidence={
            "on_time_payments_12m": profile.on_time_payments_12m,
            "min_on_time_payments": minimum,
        },
    )


def _payment_reminder(profile: CustomerProfile, policy: Policy) -> _Match | None:
    if profile.bill_status is not BillStatus.OVERDUE:
        return None
    reason = ReasonCode(
        code="PAYMENT_OVERDUE",
        description="The current bill is overdue.",
        evidence={
            "bill_status": profile.bill_status.value,
            "days_overdue": profile.days_overdue,
            "amount_due": str(profile.amount_due),
            "due_date": profile.due_date.isoformat() if profile.due_date else None,
        },
    )
    return _Match(SegmentName.PAYMENT_REMINDER, 1.0, (reason,))


def _dormant(profile: CustomerProfile, policy: Policy) -> _Match | None:
    threshold = _dec(policy.segments.thresholds.dormant_max_activity)
    activity = _dec(profile.activity_score_30d)
    if not activity < threshold:
        return None
    reason = ReasonCode(
        code="LOW_ACTIVITY",
        description="Activity in the last 30 days is below the dormant threshold.",
        evidence={
            "activity_score_30d": profile.activity_score_30d,
            "dormant_max_activity": float(threshold),
        },
    )
    return _Match(
        SegmentName.DORMANT, _below(activity, threshold, SCORE_MIN), (reason,)
    )


def _declining(profile: CustomerProfile, policy: Policy) -> _Match | None:
    threshold = _dec(policy.segments.thresholds.declining_min_drop_pct)
    drop = drop_pct(profile)
    if drop is None or drop < threshold:
        return None
    reason = ReasonCode(
        code="ACTIVITY_DROP",
        description=(
            "Activity fell by at least the declining threshold versus the "
            "previous 30 days."
        ),
        evidence={
            "activity_score_30d": profile.activity_score_30d,
            "activity_score_prev_30d": profile.activity_score_prev_30d,
            "drop_pct": float(round(drop, 2)),
            "declining_min_drop_pct": float(threshold),
        },
    )
    return _Match(
        SegmentName.DECLINING, _at_least(drop, threshold, DROP_PCT_MAX), (reason,)
    )


def _loyalty(profile: CustomerProfile, policy: Policy) -> _Match | None:
    t = policy.segments.thresholds
    months = _dec(profile.months_active)
    on_time = _dec(profile.on_time_payments_12m)
    activity = _dec(profile.activity_score_30d)
    min_months = _dec(t.loyalty_min_months_active)
    min_on_time = _dec(t.loyalty_min_on_time_payments)
    min_activity = _dec(t.loyalty_min_activity)
    if (
        months < min_months
        or on_time < min_on_time
        or activity < min_activity
        or profile.bill_status is BillStatus.OVERDUE
    ):
        return None
    reasons = (
        ReasonCode(
            code="LONG_TENURE",
            description="Tenure meets the loyalty minimum.",
            evidence={
                "months_active": profile.months_active,
                "loyalty_min_months_active": t.loyalty_min_months_active,
            },
        ),
        _on_time_reason(profile, t.loyalty_min_on_time_payments),
        ReasonCode(
            code="HIGH_ACTIVITY",
            description="Activity in the last 30 days meets the loyalty minimum.",
            evidence={
                "activity_score_30d": profile.activity_score_30d,
                "loyalty_min_activity": t.loyalty_min_activity,
            },
        ),
        _not_overdue_reason(profile),
    )
    confidence = min(
        _at_least(months, min_months, None),
        _at_least(on_time, min_on_time, ON_TIME_MAX),
        _at_least(activity, min_activity, SCORE_MAX),
    )
    return _Match(SegmentName.LOYALTY_CANDIDATE, confidence, reasons)


def _consistent(profile: CustomerProfile, policy: Policy) -> _Match | None:
    t = policy.segments.thresholds
    on_time = _dec(profile.on_time_payments_12m)
    activity = _dec(profile.activity_score_30d)
    min_on_time = _dec(t.consistent_min_on_time_payments)
    min_activity = _dec(t.consistent_min_activity)
    if (
        on_time < min_on_time
        or activity < min_activity
        or profile.bill_status is BillStatus.OVERDUE
    ):
        return None
    reasons = (
        _on_time_reason(profile, t.consistent_min_on_time_payments),
        ReasonCode(
            code="STEADY_ACTIVITY",
            description="Activity in the last 30 days meets the consistent minimum.",
            evidence={
                "activity_score_30d": profile.activity_score_30d,
                "consistent_min_activity": t.consistent_min_activity,
            },
        ),
        _not_overdue_reason(profile),
    )
    confidence = min(
        _at_least(on_time, min_on_time, ON_TIME_MAX),
        _at_least(activity, min_activity, SCORE_MAX),
    )
    return _Match(SegmentName.CONSISTENT, confidence, reasons)


_RULES = {
    SegmentName.PAYMENT_REMINDER: _payment_reminder,
    SegmentName.DORMANT: _dormant,
    SegmentName.DECLINING: _declining,
    SegmentName.LOYALTY_CANDIDATE: _loyalty,
    SegmentName.CONSISTENT: _consistent,
}


def classify_profile(profile: CustomerProfile, policy: Policy) -> ClassificationResult:
    """Every matching segment, ordered by configured priority; the first is primary."""
    matches = [
        match
        for segment in policy.segments.priority
        if (match := _RULES[segment](profile, policy)) is not None
    ]
    return ClassificationResult(
        customer_id=profile.customer_id,
        as_of_date=policy.policy.as_of_date,
        segments=[m.assignment() for m in matches],
        primary_segment=matches[0].segment if matches else None,
        policy_versions=policy.versions,
    )
