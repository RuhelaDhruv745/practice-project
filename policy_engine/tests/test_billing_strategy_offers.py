"""Reminder stages, billing consistency, strategy mapping and offer eligibility."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from contracts.enums import BlockReason, SegmentName
from policy_engine.billing.reminders import billing_issues, reminder_stage
from policy_engine.eligibility.offers import check_offers, select_offer
from policy_engine.engine import RuleBasedPolicyEngine
from policy_engine.strategies.selector import select_strategy

S = SegmentName
AS_OF = date(2026, 11, 28)

# --- reminder stages ----------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "stage"),
    [
        (0, None),
        (1, "courteous"),
        (7, "courteous"),
        (8, "firm"),
        (21, "firm"),
        (22, "final_notice"),
        (365, "final_notice"),
    ],
)
def test_reminder_stage_boundaries(policy, days, stage) -> None:
    found = reminder_stage(policy, days)
    assert (found.name if found else None) == stage


@pytest.mark.parametrize(
    ("days", "stage", "tone"),
    [
        (7, "courteous", "courteous"),
        (8, "firm", "firm_respectful"),
        (21, "firm", "firm_respectful"),
        (22, "final_notice", "final_respectful"),
    ],
)
def test_decide_reminder_stage_and_tone(
    engine, make_profile, overdue, days, stage, tone
) -> None:
    profile = make_profile(
        **{**overdue, "days_overdue": days, "due_date": AS_OF - timedelta(days=days)}
    )
    decision = engine.decide(profile)
    assert decision.facts is not None and decision.facts.reminder is not None
    assert decision.facts.reminder.stage == stage
    assert decision.facts.tone == tone == decision.strategy.tone
    assert decision.facts.reminder.amount_due == Decimal("2000.00")
    assert decision.facts.reminder.support_path == engine.policy.reminders.support_path


# --- billing consistency ------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {"bill_status": "paid", "days_overdue": 3},
            [BlockReason.CONTRADICTORY_BILLING_DATA],
        ),
        (
            {"bill_status": "due", "days_overdue": 2},
            [BlockReason.CONTRADICTORY_BILLING_DATA],
        ),
        (
            {
                "bill_status": "overdue",
                "days_overdue": 0,
                "amount_due": Decimal("10.00"),
                "due_date": date(2026, 11, 20),
            },
            [BlockReason.CONTRADICTORY_BILLING_DATA],
        ),
        (
            {
                "bill_status": "overdue",
                "days_overdue": 4,
                "amount_due": Decimal("0.00"),
                "due_date": date(2026, 11, 24),
            },
            [BlockReason.CONTRADICTORY_BILLING_DATA],
        ),
        (
            {
                "bill_status": "overdue",
                "days_overdue": 4,
                "amount_due": Decimal("10.00"),
                "due_date": AS_OF,
            },
            [BlockReason.CONTRADICTORY_BILLING_DATA],
        ),
        (
            {
                "bill_status": "overdue",
                "days_overdue": 4,
                "amount_due": Decimal("10.00"),
                "due_date": None,
            },
            [BlockReason.MISSING_EVIDENCE],
        ),
        (
            {
                "bill_status": "overdue",
                "days_overdue": 4,
                "amount_due": Decimal("10.00"),
                "due_date": date(2026, 11, 24),
            },
            [],
        ),
        (
            {
                "bill_status": "due",
                "days_overdue": 0,
                "amount_due": Decimal("499.00"),
                "due_date": date(2026, 12, 5),
            },
            [],
        ),
        ({}, []),
    ],
)
def test_billing_issues(policy, make_profile, overrides, expected) -> None:
    assert billing_issues(make_profile(**overrides), policy) == expected


# --- strategies ---------------------------------------------------------------


def test_strategy_from_yaml(policy) -> None:
    strategy = select_strategy(policy, S.LOYALTY_CANDIDATE)
    assert strategy.objective == "reward"
    assert strategy.tone == "celebratory"
    assert strategy.tone_guidance == policy.strategies.tones["celebratory"]
    assert strategy.offer_allowed is True


def test_reminder_stage_tone_overrides_strategy_tone(policy) -> None:
    final = reminder_stage(policy, 30)
    strategy = select_strategy(policy, S.PAYMENT_REMINDER, final)
    assert strategy.tone == "final_respectful"
    assert strategy.objective == "collect_politely"
    assert strategy.offer_allowed is False


def test_editing_strategies_yaml_changes_strategy(make_profile, policy_with) -> None:
    def change(files) -> None:
        files["strategies"]["strategies"]["consistent"]["tone"] = "friendly_helpful"
        files["strategies"]["strategies"]["consistent"]["objective"] = "check_in"

    engine = RuleBasedPolicyEngine(policy_with(change))
    decision = engine.decide(make_profile())
    assert decision.strategy.objective == "check_in"
    assert decision.facts.tone == "friendly_helpful"


# --- offers -------------------------------------------------------------------


def _loyal(make_profile, **overrides):
    return make_profile(
        **{
            "months_active": 24,
            "activity_score_30d": 80.0,
            "activity_score_prev_30d": 80.0,
            **overrides,
        }
    )


def test_one_check_per_configured_offer(engine, make_profile) -> None:
    decision = engine.decide(_loyal(make_profile))
    assert [c.offer_id for c in decision.offer_checks] == [
        o.offer_id for o in engine.policy.offers.offers
    ]
    eligible = [c.offer_id for c in decision.offer_checks if c.eligible]
    assert eligible == ["LOYAL-10GB"]
    assert decision.facts.offer.offer_id == "LOYAL-10GB"
    assert decision.facts.offer.value == Decimal("10")
    others = {
        c.offer_id: c.failed_rules for c in decision.offer_checks if not c.eligible
    }
    assert others == {
        "REENGAGE-20": ["segment_not_allowed"],
        "WINBACK-300": ["segment_not_allowed"],
    }


@pytest.mark.parametrize(("months", "failed"), [(23, ["min_tenure"]), (24, [])])
def test_offer_min_tenure_boundary(policy, make_profile, months, failed) -> None:
    # Checked directly: at 23 months the customer is not loyalty_candidate at all.
    strategy = select_strategy(policy, S.LOYALTY_CANDIDATE)
    profile = _loyal(make_profile, months_active=months)
    checks = check_offers(profile, policy, S.LOYALTY_CANDIDATE, strategy)
    assert checks[0].offer_id == "LOYAL-10GB"
    assert checks[0].failed_rules == failed
    assert checks[0].eligible is (not failed)


def test_declining_offer_tenure_boundary(engine, make_profile) -> None:
    def decide(months: int):
        return engine.decide(
            make_profile(
                months_active=months,
                activity_score_30d=30.0,
                activity_score_prev_30d=60.0,
            )
        )

    short, ok = decide(2), decide(3)
    assert short.facts.offer is None
    assert short.offer_checks[1].failed_rules == ["min_tenure"]
    assert ok.facts.offer.offer_id == "REENGAGE-20"


@pytest.mark.parametrize(
    ("expiry", "eligible"),
    [
        (AS_OF, True),
        (AS_OF - timedelta(days=1), False),
        (AS_OF + timedelta(days=1), True),
    ],
)
def test_offer_expiry_on_as_of_date(
    make_profile, policy_with, expiry, eligible
) -> None:
    def set_expiry(files) -> None:
        files["offers"]["offers"][0]["expiry"] = expiry

    engine = RuleBasedPolicyEngine(policy_with(set_expiry))
    decision = engine.decide(_loyal(make_profile))
    check = decision.offer_checks[0]
    assert check.eligible is eligible
    assert ("expired" in check.failed_rules) is not eligible
    assert (decision.facts.offer is not None) is eligible


def test_offer_wrong_channel_is_ineligible(make_profile, policy_with) -> None:
    def to_sms(files) -> None:
        files["offers"]["offers"][0]["channel"] = "sms"

    engine = RuleBasedPolicyEngine(policy_with(to_sms))
    decision = engine.decide(_loyal(make_profile))
    assert decision.offer_checks[0].failed_rules == ["channel"]
    assert decision.facts.offer is None


def test_strategy_without_offers_gets_no_offer(policy, make_profile) -> None:
    strategy = select_strategy(policy, S.CONSISTENT)
    checks = check_offers(
        make_profile(months_active=40), policy, S.CONSISTENT, strategy
    )
    assert all("strategy_disallows_offers" in c.failed_rules for c in checks)
    assert select_offer(policy, checks) is None


def test_at_most_one_offer_when_several_pass(make_profile, policy_with) -> None:
    def duplicate(files) -> None:
        extra = dict(files["offers"]["offers"][0], offer_id="LOYAL-5GB", value=5)
        files["offers"]["offers"].append(extra)

    engine = RuleBasedPolicyEngine(policy_with(duplicate))
    decision = engine.decide(_loyal(make_profile))
    assert sum(c.eligible for c in decision.offer_checks) == 2
    assert decision.facts.offer.offer_id == "LOYAL-10GB"  # first in YAML order
