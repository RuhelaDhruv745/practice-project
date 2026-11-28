"""Segment to approved ``Strategy`` from ``data/policies/strategies.yaml``.

For ``payment_reminder`` the reminder stage tone (``reminders.yaml``) overrides the
strategy's fallback tone, so a 30-day overdue bill never gets a courteous tone.
"""

from __future__ import annotations

from contracts.enums import SegmentName
from contracts.models import Strategy
from policy_engine.config_loader import Policy, ReminderStage


def select_strategy(
    policy: Policy, segment: SegmentName, stage: ReminderStage | None = None
) -> Strategy:
    configured = policy.strategies.strategies[segment]
    tone = configured.tone
    if segment is SegmentName.PAYMENT_REMINDER and stage is not None:
        tone = stage.tone
    return Strategy(
        segment=segment,
        objective=configured.objective,
        tone=tone,
        tone_guidance=policy.strategies.tones[tone],
        offer_allowed=configured.offer_allowed,
    )
