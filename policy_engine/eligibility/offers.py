"""Offer eligibility: one ``OfferCheck`` per configured offer, at most one in facts.

Failed rule names (stable, shown to reviewers):

- ``segment_not_allowed``: the primary segment is not in ``allowed_segments``.
- ``strategy_disallows_offers``: the primary segment's strategy has
  ``offer_allowed: false`` (or there is no primary segment).
- ``min_tenure``: ``months_active < min_months_active``.
- ``expired``: ``expiry < as_of_date`` (an offer expiring on ``as_of_date`` is valid).
- ``channel``: the offer's channel is not the outreach channel (email).

When several offers pass, the first in ``offers.yaml`` order goes into the facts.
"""

from __future__ import annotations

from contracts.enums import Channel, SegmentName
from contracts.models import CustomerProfile, OfferCheck, OfferSnapshot, Strategy
from policy_engine.config_loader import Offer, Policy

# The product only drafts emails (mock outbox); this is the delivery channel, not policy.
OUTREACH_CHANNEL = Channel.EMAIL


def _failed_rules(
    offer: Offer,
    profile: CustomerProfile,
    policy: Policy,
    segment: SegmentName | None,
    strategy: Strategy | None,
) -> list[str]:
    failed: list[str] = []
    if segment is None or segment not in offer.allowed_segments:
        failed.append("segment_not_allowed")
    if strategy is None or not strategy.offer_allowed:
        failed.append("strategy_disallows_offers")
    if profile.months_active < offer.min_months_active:
        failed.append("min_tenure")
    if offer.expiry < policy.policy.as_of_date:
        failed.append("expired")
    if offer.channel is not OUTREACH_CHANNEL:
        failed.append("channel")
    return failed


def check_offers(
    profile: CustomerProfile,
    policy: Policy,
    segment: SegmentName | None,
    strategy: Strategy | None,
) -> list[OfferCheck]:
    checks = []
    for offer in policy.offers.offers:
        failed = _failed_rules(offer, profile, policy, segment, strategy)
        checks.append(
            OfferCheck(
                offer_id=offer.offer_id, eligible=not failed, failed_rules=failed
            )
        )
    return checks


def select_offer(policy: Policy, checks: list[OfferCheck]) -> OfferSnapshot | None:
    """Snapshot of the first eligible offer, copied exactly from configuration."""
    eligible = {check.offer_id for check in checks if check.eligible}
    for offer in policy.offers.offers:
        if offer.offer_id in eligible:
            return OfferSnapshot(
                offer_id=offer.offer_id,
                description=offer.description,
                value=offer.value,
                unit=offer.unit,
                expiry=offer.expiry,
                channel=offer.channel,
            )
    return None
