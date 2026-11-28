"""Billing consistency checks, reminder stage selection and ``ReminderFacts``.

Consistency rules (any hit blocks all outreach for the customer, because a record we
cannot trust must not drive any message):

- ``contradictory_billing_data``: ``paid`` or ``due`` with ``days_overdue > 0``;
  ``overdue`` with ``days_overdue == 0`` or ``amount_due == 0``; ``overdue`` with a
  ``due_date`` that is not before ``as_of_date``.
- ``missing_evidence``: ``overdue`` with no ``due_date``.

Stage selection uses the contiguous day ranges in ``data/policies/reminders.yaml``.
"""

from __future__ import annotations

from contracts.enums import BillStatus, BlockReason
from contracts.models import CustomerProfile, ReminderFacts
from policy_engine.config_loader import Policy, ReminderStage


def billing_issues(profile: CustomerProfile, policy: Policy) -> list[BlockReason]:
    """Block reasons caused by an inconsistent or incomplete billing record."""
    reasons: list[BlockReason] = []
    as_of = policy.policy.as_of_date
    if profile.bill_status is BillStatus.OVERDUE:
        contradictory = (
            profile.days_overdue == 0
            or profile.amount_due == 0
            or (profile.due_date is not None and profile.due_date >= as_of)
        )
        if contradictory:
            reasons.append(BlockReason.CONTRADICTORY_BILLING_DATA)
        if profile.due_date is None:
            reasons.append(BlockReason.MISSING_EVIDENCE)
    elif profile.days_overdue > 0:
        reasons.append(BlockReason.CONTRADICTORY_BILLING_DATA)
    return reasons


def reminder_stage(policy: Policy, days_overdue: int) -> ReminderStage | None:
    """The configured stage whose day range contains ``days_overdue``, if any."""
    for stage in policy.reminders.stages:
        upper_ok = stage.max_days is None or days_overdue <= stage.max_days
        if stage.min_days <= days_overdue and upper_ok:
            return stage
    return None


def build_reminder_facts(
    profile: CustomerProfile, policy: Policy, stage: ReminderStage
) -> ReminderFacts:
    """Exact billing facts a reminder must quote. Call only after billing_issues is empty."""
    if profile.due_date is None:
        raise ValueError("reminder facts need a due_date; check billing_issues first")
    return ReminderFacts(
        stage=stage.name,
        days_overdue=profile.days_overdue,
        amount_due=profile.amount_due,
        currency=policy.policy.currency,
        due_date=profile.due_date,
        support_path=policy.reminders.support_path,
    )
