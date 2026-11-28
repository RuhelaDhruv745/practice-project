"""Deterministic implementation of ``contracts.interfaces.PolicyEngine``.

``decide`` runs, in order: classification, billing consistency, strategy (with the
reminder stage tone), offer checks, then the outreach gates. Every gate that fails is
recorded; block reasons are listed in a fixed order so output is reproducible:

1. ``contradictory_billing_data`` / ``missing_evidence`` (see ``billing.reminders``)
2. ``no_actionable_segment``: no segment matched
3. ``no_marketing_consent``: ``consent_marketing`` is false, unless the primary segment
   is ``payment_reminder`` and ``reminders_require_marketing_consent`` is false
4. ``contacted_too_recently``: ``last_contacted_days_ago < min_days_between_contacts``
   (applies to reminders too; ``None`` means never contacted)

No LLM, no system clock (``as_of_date`` comes from ``policy.yaml``), no randomness.
"""

from __future__ import annotations

from pathlib import Path

from contracts.enums import BlockReason, DecisionStatus, SegmentName
from contracts.models import (
    ClassificationResult,
    CustomerProfile,
    DraftContent,
    OfferSnapshot,
    PolicyDecision,
    ReminderFacts,
    Strategy,
    ValidationResult,
    VerifiedFacts,
)
from policy_engine.billing.reminders import (
    billing_issues,
    build_reminder_facts,
    reminder_stage,
)
from policy_engine.classification.segmenter import classify_profile
from policy_engine.config_loader import DEFAULT_CONFIG_DIR, Policy, load_policy
from policy_engine.eligibility.offers import check_offers, select_offer
from policy_engine.strategies.selector import select_strategy

_REASON_ORDER = (
    BlockReason.CONTRADICTORY_BILLING_DATA,
    BlockReason.MISSING_EVIDENCE,
    BlockReason.NO_ACTIONABLE_SEGMENT,
    BlockReason.NO_MARKETING_CONSENT,
    BlockReason.CONTACTED_TOO_RECENTLY,
)


class RuleBasedPolicyEngine:
    """Policy engine built from one validated ``Policy`` (``config_loader``)."""

    def __init__(self, policy: Policy) -> None:
        self.policy = policy

    @classmethod
    def from_config_dir(
        cls, config_dir: Path | str = DEFAULT_CONFIG_DIR
    ) -> RuleBasedPolicyEngine:
        return cls(load_policy(config_dir))

    def classify(self, profile: CustomerProfile) -> ClassificationResult:
        return classify_profile(profile, self.policy)

    def decide(self, profile: CustomerProfile) -> PolicyDecision:
        classification = self.classify(profile)
        primary = classification.primary_segment

        reasons = set(billing_issues(profile, self.policy))
        if primary is None:
            reasons.add(BlockReason.NO_ACTIONABLE_SEGMENT)
        if not self._consent_ok(profile, primary):
            reasons.add(BlockReason.NO_MARKETING_CONSENT)
        if self._contacted_too_recently(profile):
            reasons.add(BlockReason.CONTACTED_TOO_RECENTLY)

        stage = None
        if primary is SegmentName.PAYMENT_REMINDER:
            stage = reminder_stage(self.policy, profile.days_overdue)
        strategy = (
            select_strategy(self.policy, primary, stage)
            if primary is not None
            else None
        )
        offer_checks = check_offers(profile, self.policy, primary, strategy)

        if reasons:
            return PolicyDecision(
                customer_id=profile.customer_id,
                status=DecisionStatus.BLOCKED,
                block_reasons=[r for r in _REASON_ORDER if r in reasons],
                classification=classification,
                strategy=strategy,
                offer_checks=offer_checks,
            )

        # Gates passed: primary is set and, for reminders, billing is consistent.
        if primary is None or strategy is None:  # unreachable: no_actionable_segment
            raise ValueError("an allowed decision needs a primary segment")
        reminder: ReminderFacts | None = None
        if primary is SegmentName.PAYMENT_REMINDER:
            if stage is None:  # unreachable once billing_issues passed
                raise ValueError("no reminder stage for a consistent overdue bill")
            reminder = build_reminder_facts(profile, self.policy, stage)
        offer = select_offer(self.policy, offer_checks)
        return PolicyDecision(
            customer_id=profile.customer_id,
            status=DecisionStatus.DRAFT_ALLOWED,
            classification=classification,
            strategy=strategy,
            offer_checks=offer_checks,
            facts=build_verified_facts(profile, strategy, offer, reminder),
        )

    def validate(
        self, draft: DraftContent, decision: PolicyDecision
    ) -> ValidationResult:
        raise NotImplementedError(
            "draft validators (FR-07) are planned for Sprint 2 in policy_engine/compliance"
        )

    def _consent_ok(
        self, profile: CustomerProfile, primary: SegmentName | None
    ) -> bool:
        if profile.consent_marketing:
            return True
        exempt = not self.policy.policy.contact.reminders_require_marketing_consent
        return exempt and primary is SegmentName.PAYMENT_REMINDER

    def _contacted_too_recently(self, profile: CustomerProfile) -> bool:
        days = profile.last_contacted_days_ago
        minimum = self.policy.policy.contact.min_days_between_contacts
        return days is not None and days < minimum


def build_verified_facts(
    profile: CustomerProfile,
    strategy: Strategy,
    offer: OfferSnapshot | None,
    reminder: ReminderFacts | None,
) -> VerifiedFacts:
    """Only what the writer needs. No billing history, scores, consent or tenure."""
    return VerifiedFacts(
        customer_id=profile.customer_id,
        first_name=profile.first_name,
        plan=profile.plan,
        segment=strategy.segment,
        objective=strategy.objective,
        tone=strategy.tone,
        tone_guidance=strategy.tone_guidance,
        offer=offer,
        reminder=reminder,
    )
