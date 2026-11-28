"""Hand-built VerifiedFacts per segment (Member 3's decide is not merged yet).

Values mirror data/policies/*.yaml but are typed in here so these tests do not depend
on the policy loader. Tests never call a real LLM API.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from contracts.enums import Channel, OfferUnit, SegmentName
from contracts.models import OfferSnapshot, ReminderFacts, VerifiedFacts

SUPPORT_PATH = (
    "If you have already paid or believe this bill is wrong, call support on "
    "1800-000-0000 or reply to this email to raise a dispute."
)


def make_facts(**overrides: object) -> VerifiedFacts:
    base: dict[str, object] = {
        "customer_id": "CUST-001",
        "first_name": "Asha",
        "plan": "Unlimited 599",
        "segment": SegmentName.CONSISTENT,
        "objective": "thank",
        "tone": "warm_appreciative",
        "tone_guidance": "Warm and grateful. Thank the customer. No sales push.",
    }
    base.update(overrides)
    return VerifiedFacts(**base)


def reward_offer() -> OfferSnapshot:
    return OfferSnapshot(
        offer_id="LOYAL-10GB",
        description="bonus data added to your current plan",
        value=Decimal("10"),
        unit=OfferUnit.GB,
        expiry=date(2027, 1, 31),
        channel=Channel.EMAIL,
    )


def reengage_offer() -> OfferSnapshot:
    return OfferSnapshot(
        offer_id="REENGAGE-20",
        description="off your next add-on pack",
        value=Decimal("20"),
        unit=OfferUnit.PERCENT,
        expiry=date(2026, 12, 31),
        channel=Channel.EMAIL,
    )


def winback_offer() -> OfferSnapshot:
    return OfferSnapshot(
        offer_id="WINBACK-300",
        description="off your next recharge",
        value=Decimal("300"),
        unit=OfferUnit.INR,
        expiry=date(2027, 1, 15),
        channel=Channel.EMAIL,
    )


def reminder(stage: str = "courteous", days: int = 5) -> ReminderFacts:
    return ReminderFacts(
        stage=stage,
        days_overdue=days,
        amount_due=Decimal("749.00"),
        currency="INR",
        due_date=date(2026, 11, 20),
        support_path=SUPPORT_PATH,
    )


def all_segment_facts() -> list[VerifiedFacts]:
    """Thanks, reward, re-engage, win-back and each reminder stage."""
    return [
        make_facts(),
        make_facts(
            segment=SegmentName.LOYALTY_CANDIDATE,
            objective="reward",
            tone="celebratory",
            tone_guidance="Upbeat and appreciative.",
            offer=reward_offer(),
        ),
        make_facts(
            segment=SegmentName.DECLINING,
            objective="re_engage",
            tone="friendly_helpful",
            tone_guidance="Friendly and helpful.",
            offer=reengage_offer(),
        ),
        make_facts(
            segment=SegmentName.DORMANT,
            objective="win_back",
            tone="gentle",
            tone_guidance="Gentle and low-pressure.",
            offer=winback_offer(),
        ),
        *[
            make_facts(
                segment=SegmentName.PAYMENT_REMINDER,
                objective="collect_politely",
                tone=tone,
                tone_guidance="Respectful.",
                reminder=reminder(stage, days),
            )
            for stage, tone, days in [
                ("courteous", "courteous", 3),
                ("firm", "firm_respectful", 10),
                ("final", "final_respectful", 30),
            ]
        ],
    ]


def reward_facts() -> VerifiedFacts:
    return all_segment_facts()[1]


def reminder_facts() -> VerifiedFacts:
    return make_facts(
        customer_id="CUST-005",
        segment=SegmentName.PAYMENT_REMINDER,
        objective="collect_politely",
        tone="courteous",
        tone_guidance="Polite, assumes an oversight. Brief and helpful.",
        reminder=reminder(),
    )
